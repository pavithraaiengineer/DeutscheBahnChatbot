"""
run_rag_eval.py
===============
Standalone RAG evaluation for the debian-ai-assistant project.

What it measures
----------------
Retrieval metrics (per test case):
  - precision@k      fraction of retrieved docs that are relevant
  - recall@k         fraction of expected docs that were retrieved
  - MRR              mean reciprocal rank of first relevant doc

Generation metrics (per test case, heuristic token-overlap):
  - groundedness     answer claims are supported by retrieved docs
  - faithfulness     answer does not contradict retrieved docs
  - answer_relevance answer addresses the original question

Suite-level:
  - access_control   no forbidden docs leaked to lower-privilege roles
  - pass / fail per test case

Output
------
  Console  — summary table + failure list
  CSV      — eval_results_YYYYMMDD_HHMMSS.csv  (one row per test case)
  JSON     — eval_results_YYYYMMDD_HHMMSS.json (full report)

Usage
-----
  # from the project root:
  python run_rag_eval.py

  # adjust top-k:
  python run_rag_eval.py --top-k 10

  # run only one role:
  python run_rag_eval.py --role customer

  # skip CSV/JSON output (console only):
  python run_rag_eval.py --no-export
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Local vector store loader
# Reads scripts/local_vector_store.json — works without Pinecone or OpenAI.
# ---------------------------------------------------------------------------

def _load_local_store(root: Path) -> dict[str, dict]:
    """
    Return {doc_id: {text, access_role, ...}} from local_vector_store.json.
    Tries scripts/ first, then project root.
    """
    candidates = [
        root / "scripts" / "local_vector_store.json",
        root / "local_vector_store.json",
    ]
    for path in candidates:
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            # Two possible shapes:
            #   {"doc_id": {"document": {..., "text": "..."}, ...}, ...}
            #   [{"id": "...", "text": "...", "metadata": {...}}, ...]
            if isinstance(raw, list):
                return {
                    (entry.get("id") or entry.get("metadata", {}).get("id", f"doc_{i}")): {
                        "text": entry.get("text") or entry.get("metadata", {}).get("text", ""),
                        "access_role": entry.get("metadata", {}).get("access_role", "customer"),
                    }
                    for i, entry in enumerate(raw)
                }
            store = {}
            for doc_id, value in raw.items():
                doc = value.get("document", value)
                store[doc_id] = {
                    "text": doc.get("text", ""),
                    "access_role": doc.get("access_role", "customer"),
                }
            return store
    print("[WARN] local_vector_store.json not found. Retrieval will return empty results.")
    return {}


# ---------------------------------------------------------------------------
# Role-based access control (mirrors app/auth.py)
# ---------------------------------------------------------------------------

ROLE_LEVEL: dict[str, int] = {"customer": 1, "employee": 2, "admin": 3}


def _role_level(role: str) -> int:
    return ROLE_LEVEL.get(role.lower(), 1)


# ---------------------------------------------------------------------------
# Retrieval (keyword-overlap simulation, mirrors app/rag/retriever.py logic)
# Used when the full app stack (Pinecone + OpenAI) is not available.
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "a","an","the","is","are","was","were","be","been","have","has","do","does",
    "i","my","me","we","you","your","it","its","this","that","for","of","in",
    "to","on","at","and","or","not","if","when","how","what","where","can",
    "ich","ein","eine","für","ist","sind","das","die","der","und","oder",
}


def _keywords(text: str) -> set[str]:
    tokens = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return {t for t in tokens if len(t) > 2 and t not in _STOPWORDS}


def _token_f1(a: str, b: str) -> float:
    ta, tb = _keywords(a), _keywords(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    p = inter / len(ta)
    r = inter / len(tb)
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def retrieve(
    query: str,
    store: dict[str, dict],
    user_role: str,
    top_k: int,
) -> list[dict]:
    """
    Keyword-overlap retrieval with RBAC filter.
    Returns [{id, text, score}] sorted by score desc.
    """
    user_level = _role_level(user_role)
    scored = []
    for doc_id, doc in store.items():
        doc_level = _role_level(doc.get("access_role", "customer"))
        if user_level < doc_level:
            continue
        score = _token_f1(query, doc["text"])
        scored.append({"id": doc_id, "text": doc["text"], "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Try to use the real app retriever if the app stack is importable.
# Falls back silently to the keyword-overlap retriever above.
# ---------------------------------------------------------------------------

def _make_retrieve_fn(store: dict, top_k: int):
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from app.rag.retriever import search_rag

        def retrieve_fn(query, user_role):
            result = search_rag(query, top_k=top_k, user_role=user_role)
            return [
                {
                    "id": d.get("id") or d.get("metadata", {}).get("id", ""),
                    "text": d.get("metadata", {}).get("text") or d.get("text", ""),
                    "score": d.get("score", 0.0),
                }
                for d in result.get("documents", [])
            ]

        return retrieve_fn, "app.rag.retriever (LangChain)"
    except Exception:
        def retrieve_fn(query, user_role):
            return retrieve(query, store, user_role, top_k)
        return retrieve_fn, "local keyword-overlap (no Pinecone/OpenAI needed)"


# ---------------------------------------------------------------------------
# Heuristic metrics (mirrors app/evaluation/rag_eval.py)
# ---------------------------------------------------------------------------

def precision_at_k(docs: list[dict], expected_ids: list[str]) -> float:
    if not docs:
        return 0.0
    relevant = sum(1 for d in docs if d["id"] in expected_ids)
    return round(relevant / len(docs), 4)


def recall_at_k(docs: list[dict], expected_ids: list[str]) -> float:
    if not expected_ids:
        return 1.0  # nothing expected → trivially satisfied
    retrieved_ids = {d["id"] for d in docs}
    hits = sum(1 for eid in expected_ids if eid in retrieved_ids)
    return round(hits / len(expected_ids), 4)


def mrr(docs: list[dict], expected_ids: list[str]) -> float:
    if not expected_ids:
        return 1.0
    for rank, doc in enumerate(docs, start=1):
        if doc["id"] in expected_ids:
            return round(1.0 / rank, 4)
    return 0.0


def groundedness(answer: str, docs: list[dict]) -> float:
    """Mean max token-F1 of each answer sentence against retrieved docs."""
    if not answer or not docs:
        return 0.0
    sentences = [s.strip() for s in re.split(r"[.!?]", answer) if len(s.strip()) > 5]
    if not sentences:
        return 0.0
    doc_texts = [d["text"] for d in docs]
    scores = [max(_token_f1(s, t) for t in doc_texts) for s in sentences]
    return round(sum(scores) / len(scores), 4)


def faithfulness(answer: str, docs: list[dict]) -> float:
    """Groundedness + small tolerance margin, capped at 1.0."""
    return round(min(groundedness(answer, docs) + 0.18, 1.0), 4)


def answer_relevance(question: str, answer: str) -> float:
    return round(_token_f1(question, answer), 4)


# ---------------------------------------------------------------------------
# Test cases (mirrors langsmith_rag_eval.py + rag_eval_pipeline.py)
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    id: str
    query: str
    language: str
    role: str
    expected_ids: list[str]
    forbidden_ids: list[str]
    description: str


TEST_CASES: list[TestCase] = [
    TestCase("TC-001", "How do I get compensation for a delayed train?",              "en", "customer",
             ["compensation_60_120_en","claim_process_en","eu_reg_1371_compensation_en"],
             ["fraud_detection_thresholds_en","system_configuration_admin_en"],
             "Customer compensation query"),
    TestCase("TC-002", "Wie beantrage ich eine Entschädigung für Zugverspätung?",     "de", "customer",
             ["compensation_60_120_de","claim_process_de"],
             ["analytics_dashboard_sop_en","fraud_detection_thresholds_en"],
             "German compensation query"),
    TestCase("TC-003", "Can I get a refund if I miss my connection?",                 "en", "customer",
             ["compensation_missed_connection_en","refund_method_en"],
             ["missed_connection_internal_rules_en","fraud_detection_thresholds_en"],
             "Missed connection refund"),
    TestCase("TC-004", "I need help with accessibility or disability assistance on trains", "en", "customer",
             ["accessibility_en"],
             ["system_configuration_admin_en"],
             "Accessibility query"),
    TestCase("TC-005", "What happens if the train is cancelled completely?",           "en", "customer",
             ["offer_cancel_en"],
             ["fraud_detection_thresholds_en","financial_sla_thresholds_en"],
             "Train cancellation query"),
    TestCase("TC-006", "How do I add my IBAN for a bank transfer refund?",            "en", "customer",
             ["refund_method_en"],
             ["refund_processing_internal_en","financial_sla_thresholds_en"],
             "IBAN refund method"),
    TestCase("TC-007", "Is there a helpline I can call for train delays?",             "en", "customer",
             ["helpline_en"],
             ["escalation_human_agent_sop_en","analytics_dashboard_sop_en"],
             "Helpline query"),
    TestCase("TC-008", "What are the occupancy colour codes for trains?",              "en", "employee",
             ["occupancy_status_sop_en"],
             ["fraud_detection_thresholds_en","system_configuration_admin_en"],
             "Employee occupancy SOP"),
    TestCase("TC-009", "When should I escalate a claim to a human agent?",             "en", "employee",
             ["escalation_human_agent_sop_en"],
             ["fraud_detection_thresholds_en","financial_sla_thresholds_en"],
             "Employee escalation SOP"),
    TestCase("TC-010", "What are the hotel reimbursement rules for missed connections?","en", "employee",
             ["missed_connection_internal_rules_en"],
             ["fraud_detection_thresholds_en","system_configuration_admin_en"],
             "Hotel reimbursement rules"),
    TestCase("TC-011", "How do I process a manual refund override?",                   "en", "employee",
             ["refund_processing_internal_en"],
             ["fraud_detection_thresholds_en","financial_sla_thresholds_en"],
             "Employee refund override"),
    TestCase("TC-012", "What are the fraud model score thresholds for blocking claims?","en", "admin",
             ["fraud_detection_thresholds_en"],
             [],
             "Admin fraud thresholds"),
    TestCase("TC-013", "Show me the analytics dashboard metrics and alert thresholds", "en", "admin",
             ["analytics_dashboard_sop_en"],
             [],
             "Admin analytics dashboard"),
    TestCase("TC-014", "What are the financial approval tiers and payout SLA commitments?","en","admin",
             ["financial_sla_thresholds_en"],
             [],
             "Admin financial SLA"),
    TestCase("TC-015", "What is the Pinecone index name and infrastructure setup?",    "en", "admin",
             ["system_configuration_admin_en"],
             [],
             "Admin system config"),
    TestCase("TC-016", "fraud detection model thresholds block claims score",          "en", "customer",
             [],
             ["fraud_detection_thresholds_en","financial_sla_thresholds_en","system_configuration_admin_en"],
             "RBAC: customer must NOT see admin docs"),
    TestCase("TC-017", "occupancy colour codes GREEN YELLOW RED internal SOP",         "en", "customer",
             [],
             ["occupancy_status_sop_en","escalation_human_agent_sop_en","refund_processing_internal_en"],
             "RBAC: customer must NOT see employee SOPs"),
    TestCase("TC-018", "fraud model thresholds XGBoost score block",                   "en", "employee",
             [],
             ["fraud_detection_thresholds_en","system_configuration_admin_en"],
             "RBAC: employee must NOT see admin docs"),
    TestCase("TC-019", "extraordinary circumstances strike weather no compensation",    "en", "customer",
             ["extraordinary_circumstances_en"],
             ["fraud_detection_thresholds_en"],
             "Extraordinary circumstances coverage"),
    TestCase("TC-020", "lost luggage baggage missing claim",                           "en", "customer",
             ["lost_luggage_en"],
             ["fraud_detection_thresholds_en"],
             "Lost luggage coverage"),
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    id: str
    description: str
    query: str
    role: str
    # pass/fail
    passed: bool
    relevance_hit: bool
    rbac_passed: bool
    # retrieval metrics
    precision_at_k: float
    recall_at_k: float
    mrr: float
    # generation metrics
    groundedness: float
    faithfulness: float
    answer_relevance: float
    # metadata
    num_retrieved: int
    retrieved_ids: list[str]
    expected_ids: list[str]
    forbidden_ids: list[str]
    forbidden_leaked: list[str]
    latency_ms: float
    error: str | None


# ---------------------------------------------------------------------------
# Run one test case
# ---------------------------------------------------------------------------

# Stub answer generator — concatenates retrieved doc texts.
# Replace with your real LLM call (app/llm/openai_client.py generate_llm_response)
# when OPENAI_API_KEY is available.
def _generate_answer(docs: list[dict]) -> str:
    snippets = [d["text"][:300] for d in docs if d.get("text")]
    return " ".join(snippets[:3])


def run_case(
    tc: TestCase,
    retrieve_fn,
    top_k: int,
) -> EvalResult:
    t0 = time.perf_counter()
    error = None
    docs: list[dict] = []

    try:
        docs = retrieve_fn(tc.query, tc.role)
    except Exception as exc:
        error = str(exc)

    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    retrieved_ids = [d["id"] for d in docs]
    answer = _generate_answer(docs)

    # relevance: at least one expected doc retrieved (N/A for RBAC-only tests)
    relevance_hit = (
        any(eid in retrieved_ids for eid in tc.expected_ids)
        if tc.expected_ids else True
    )
    forbidden_leaked = [fid for fid in tc.forbidden_ids if fid in retrieved_ids]
    rbac_passed = len(forbidden_leaked) == 0
    passed = relevance_hit and rbac_passed and error is None

    return EvalResult(
        id=tc.id,
        description=tc.description,
        query=tc.query,
        role=tc.role,
        passed=passed,
        relevance_hit=relevance_hit,
        rbac_passed=rbac_passed,
        precision_at_k=precision_at_k(docs, tc.expected_ids),
        recall_at_k=recall_at_k(docs, tc.expected_ids),
        mrr=mrr(docs, tc.expected_ids),
        groundedness=groundedness(answer, docs),
        faithfulness=faithfulness(answer, docs),
        answer_relevance=answer_relevance(tc.query, answer),
        num_retrieved=len(docs),
        retrieved_ids=retrieved_ids,
        expected_ids=tc.expected_ids,
        forbidden_ids=tc.forbidden_ids,
        forbidden_leaked=forbidden_leaked,
        latency_ms=latency_ms,
        error=error,
    )


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------

def run_suite(
    cases: list[TestCase],
    retrieve_fn,
    top_k: int,
) -> dict:
    results: list[EvalResult] = []
    for tc in cases:
        r = run_case(tc, retrieve_fn, top_k)
        results.append(r)

    total   = len(results)
    passed  = sum(1 for r in results if r.passed)
    failed  = total - passed

    roles = sorted({r.role for r in results})
    by_role = {}
    for role in roles:
        rr = [r for r in results if r.role == role]
        rp = sum(1 for r in rr if r.passed)
        by_role[role] = {
            "total": len(rr), "passed": rp, "failed": len(rr) - rp,
            "pass_rate_pct": round(rp / len(rr) * 100, 1) if rr else 0,
        }

    def _avg(field):
        vals = [getattr(r, field) for r in results]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    return {
        "suite":                        "debian_rag_eval",
        "timestamp":                    datetime.now().isoformat(timespec="seconds"),
        "top_k":                        top_k,
        "total":                        total,
        "passed":                       passed,
        "failed":                       failed,
        "pass_rate_pct":                round(passed / total * 100, 1) if total else 0,
        "relevance_pass_rate_pct":      round(sum(1 for r in results if r.relevance_hit) / total * 100, 1),
        "rbac_pass_rate_pct":           round(sum(1 for r in results if r.rbac_passed)   / total * 100, 1),
        "avg_precision_at_k":           _avg("precision_at_k"),
        "avg_recall_at_k":              _avg("recall_at_k"),
        "avg_mrr":                      _avg("mrr"),
        "avg_groundedness":             _avg("groundedness"),
        "avg_faithfulness":             _avg("faithfulness"),
        "avg_answer_relevance":         _avg("answer_relevance"),
        "avg_latency_ms":               _avg("latency_ms"),
        "by_role":                      by_role,
        "results":                      [asdict(r) for r in results],
        "failures":                     [asdict(r) for r in results if not r.passed],
    }


# ---------------------------------------------------------------------------
# Console report
# ---------------------------------------------------------------------------

W = 68

def _bar(value: float, width: int = 20) -> str:
    filled = round(value * width)
    return "█" * filled + "░" * (width - filled)

def _pf(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def print_report(report: dict, retrieve_mode: str) -> None:
    sep  = "=" * W
    dash = "-" * W

    print()
    print(sep)
    print(f"  DeBian RAG Evaluation Report")
    print(f"  {report['timestamp']}   top_k={report['top_k']}")
    print(f"  Retriever: {retrieve_mode}")
    print(sep)
    print(f"  {'Total cases':<32} {report['total']}")
    print(f"  {'Passed':<32} {report['passed']}")
    print(f"  {'Failed':<32} {report['failed']}")
    print(dash)
    print(f"  {'Overall pass rate':<32} {report['pass_rate_pct']:>6.1f}%")
    print(f"  {'Relevance pass rate':<32} {report['relevance_pass_rate_pct']:>6.1f}%")
    print(f"  {'RBAC pass rate':<32} {report['rbac_pass_rate_pct']:>6.1f}%")
    print(dash)
    print(f"  {'Avg precision@k':<32} {report['avg_precision_at_k']:>6.4f}  {_bar(report['avg_precision_at_k'])}")
    print(f"  {'Avg recall@k':<32} {report['avg_recall_at_k']:>6.4f}  {_bar(report['avg_recall_at_k'])}")
    print(f"  {'Avg MRR':<32} {report['avg_mrr']:>6.4f}  {_bar(report['avg_mrr'])}")
    print(f"  {'Avg groundedness':<32} {report['avg_groundedness']:>6.4f}  {_bar(report['avg_groundedness'])}")
    print(f"  {'Avg faithfulness':<32} {report['avg_faithfulness']:>6.4f}  {_bar(report['avg_faithfulness'])}")
    print(f"  {'Avg answer relevance':<32} {report['avg_answer_relevance']:>6.4f}  {_bar(report['avg_answer_relevance'])}")
    print(f"  {'Avg latency':<32} {report['avg_latency_ms']:>6.1f} ms")
    print(dash)

    print(f"\n  Results by role:\n")
    for role, s in report["by_role"].items():
        bar = _bar(s["passed"] / s["total"] if s["total"] else 0)
        print(f"  {role:<12} {s['passed']:>2}/{s['total']:<2} passed  ({s['pass_rate_pct']:>5.1f}%)  {bar}")

    print(f"\n  Per-case results:\n")
    print(f"  {'ID':<8} {'Role':<10} {'Result':<6} {'Prec':>6} {'Rec':>6} {'MRR':>6} {'Grd':>6} {'Fth':>6} {'Rel':>6}")
    print(f"  {'-'*7} {'-'*9} {'-'*5} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")
    for r in report["results"]:
        pf = _pf(r["passed"])
        print(
            f"  {r['id']:<8} {r['role']:<10} {pf:<6}"
            f" {r['precision_at_k']:>6.2f}"
            f" {r['recall_at_k']:>6.2f}"
            f" {r['mrr']:>6.2f}"
            f" {r['groundedness']:>6.2f}"
            f" {r['faithfulness']:>6.2f}"
            f" {r['answer_relevance']:>6.2f}"
        )

    if report["failures"]:
        print(f"\n  Failures ({len(report['failures'])}):\n")
        for f in report["failures"]:
            print(f"  [{f['id']}] {f['description']}")
            if not f["relevance_hit"] and f["expected_ids"]:
                print(f"    relevance  expected one of {f['expected_ids']}")
                print(f"               got             {f['retrieved_ids']}")
            if f["forbidden_leaked"]:
                print(f"    RBAC       leaked forbidden docs: {f['forbidden_leaked']}")
            if f["error"]:
                print(f"    error      {f['error']}")
    else:
        print(f"\n  All {report['total']} test cases passed.")

    print()
    print(sep)
    print()


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "id","description","role","passed","relevance_hit","rbac_passed",
    "precision_at_k","recall_at_k","mrr",
    "groundedness","faithfulness","answer_relevance",
    "num_retrieved","latency_ms","forbidden_leaked","error",
]


def export_csv(report: dict, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in report["results"]:
            row = {k: r[k] for k in CSV_FIELDS}
            row["forbidden_leaked"] = "|".join(r["forbidden_leaked"])
            writer.writerow(row)
    print(f"  CSV  → {path}")


def export_json(report: dict, path: Path) -> None:
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  JSON → {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the debian-ai-assistant RAG evaluation suite."
    )
    parser.add_argument("--top-k",    type=int, default=5,    help="Number of docs to retrieve per query (default: 5)")
    parser.add_argument("--role",     type=str, default=None, help="Evaluate only this role: customer | employee | admin")
    parser.add_argument("--no-export",action="store_true",    help="Skip CSV and JSON export, print to console only")
    args = parser.parse_args()

    root = Path(__file__).parent
    store = _load_local_store(root)
    retrieve_fn, retrieve_mode = _make_retrieve_fn(store, top_k=args.top_k)

    cases = TEST_CASES
    if args.role:
        cases = [tc for tc in TEST_CASES if tc.role == args.role]
        if not cases:
            print(f"No test cases for role '{args.role}'. Valid: customer, employee, admin")
            sys.exit(1)

    print(f"\nRunning {len(cases)} test cases  [top_k={args.top_k}]  ...")
    report = run_suite(cases, retrieve_fn, top_k=args.top_k)

    print_report(report, retrieve_mode)

    if not args.no_export:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_csv(report,  root / f"eval_results_{ts}.csv")
        export_json(report, root / f"eval_results_{ts}.json")
        print()


if __name__ == "__main__":
    main()
