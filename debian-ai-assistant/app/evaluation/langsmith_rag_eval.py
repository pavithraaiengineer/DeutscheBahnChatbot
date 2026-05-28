"""
RAG Evaluation with LangSmith tracing.

What this does
--------------
1. Wraps each test case in a LangSmith traced run so every retrieval +
   evaluation step appears in the LangSmith UI.
2. Pushes all metric scores as LangSmith feedback so you can filter,
   compare, and chart them in the dashboard.
3. Falls back gracefully — if LANGSMITH_API_KEY is not set the suite
   still runs locally and prints results to the terminal.

Setup
-----
Add these to your .env:

    LANGSMITH_API_KEY=ls__...
    LANGSMITH_PROJECT=debian-rag-eval      # optional, defaults to "debian-rag-eval"
    LANGCHAIN_TRACING_V2=true              # enables automatic LangChain tracing

Run
---
    python -m app.evaluation.langsmith_rag_eval
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, asdict

from app.config import get_env
from app.rag.retriever import search_rag
from app.security.governance import write_evaluation_event


# ---------------------------------------------------------------------------
# LangSmith client (optional)
# ---------------------------------------------------------------------------

def _get_langsmith_client():
    """Return a LangSmith Client if configured, else None."""
    api_key = get_env("LANGSMITH_API_KEY", "")
    if not api_key:
        return None
    try:
        from langsmith import Client
        return Client(api_key=api_key)
    except ImportError:
        print("[LangSmith] langsmith package not installed. Run: pip install langsmith")
        return None


def _ensure_project(client, project_name: str) -> None:
    """Create the LangSmith project if it does not already exist."""
    try:
        client.create_project(project_name, exist_ok=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test cases (same as rag_eval_pipeline.py — single source of truth)
# ---------------------------------------------------------------------------

@dataclass
class RagTestCase:
    id: str
    query: str
    language: str
    user_role: str
    expected_doc_ids: list[str]
    forbidden_doc_ids: list[str]
    description: str = ""


RAG_TEST_CASES: list[RagTestCase] = [
    RagTestCase("TC-001", "How do I get compensation for a delayed train?",           "en", "customer",
                ["compensation_60_120_en", "claim_process_en"], ["fraud_detection_thresholds_en"],
                "Customer compensation query"),
    RagTestCase("TC-002", "Wie beantrage ich eine Entschädigung für Zugverspätung?",  "de", "customer",
                ["compensation_60_120_de", "claim_process_de"], ["analytics_dashboard_sop_en"],
                "German compensation query"),
    RagTestCase("TC-003", "Can I get a refund if I miss my connection?",              "en", "customer",
                ["compensation_missed_connection_en", "refund_method_en"], ["fraud_detection_thresholds_en"],
                "Missed connection refund"),
    RagTestCase("TC-004", "I need help with accessibility on trains",                 "en", "customer",
                ["accessibility_en"], ["system_configuration_admin_en"],
                "Accessibility query"),
    RagTestCase("TC-005", "What happens if the train is cancelled completely?",       "en", "customer",
                ["offer_cancel_en"], ["fraud_detection_thresholds_en"],
                "Cancellation query"),
    RagTestCase("TC-006", "How do I add my IBAN for a bank transfer refund?",        "en", "customer",
                ["refund_method_en"], ["financial_sla_thresholds_en"],
                "IBAN refund method"),
    RagTestCase("TC-007", "Is there a helpline I can call for train delays?",         "en", "customer",
                ["helpline_en"], ["escalation_human_agent_sop_en"],
                "Helpline query"),
    RagTestCase("TC-008", "What are the occupancy colour codes for trains?",          "en", "employee",
                ["occupancy_status_sop_en"], ["fraud_detection_thresholds_en"],
                "Employee occupancy SOP"),
    RagTestCase("TC-009", "When should I escalate a claim to a human agent?",         "en", "employee",
                ["escalation_human_agent_sop_en"], ["financial_sla_thresholds_en"],
                "Employee escalation SOP"),
    RagTestCase("TC-010", "What are the hotel reimbursement rules for missed connections?", "en", "employee",
                ["missed_connection_internal_rules_en"], ["system_configuration_admin_en"],
                "Employee missed connection rules"),
    RagTestCase("TC-011", "How do I process a manual refund override?",               "en", "employee",
                ["refund_processing_internal_en"], ["fraud_detection_thresholds_en"],
                "Employee refund override"),
    RagTestCase("TC-012", "What are the fraud model score thresholds?",               "en", "admin",
                ["fraud_detection_thresholds_en"], [],
                "Admin fraud thresholds"),
    RagTestCase("TC-013", "Show me the analytics dashboard metrics",                   "en", "admin",
                ["analytics_dashboard_sop_en"], [],
                "Admin analytics dashboard"),
    RagTestCase("TC-014", "What are the financial approval tiers and SLA commitments?","en", "admin",
                ["financial_sla_thresholds_en"], [],
                "Admin financial SLA"),
    RagTestCase("TC-015", "What is the Pinecone index name and infrastructure setup?", "en", "admin",
                ["system_configuration_admin_en"], [],
                "Admin system config"),
    RagTestCase("TC-016", "fraud detection model thresholds block claims score",       "en", "customer",
                [], ["fraud_detection_thresholds_en", "financial_sla_thresholds_en"],
                "Customer must NOT see admin docs"),
    RagTestCase("TC-017", "occupancy colour codes GREEN YELLOW RED internal SOP",     "en", "customer",
                [], ["occupancy_status_sop_en", "escalation_human_agent_sop_en"],
                "Customer must NOT see employee SOPs"),
    RagTestCase("TC-018", "fraud model thresholds XGBoost score block",               "en", "employee",
                [], ["fraud_detection_thresholds_en", "system_configuration_admin_en"],
                "Employee must NOT see admin docs"),
    RagTestCase("TC-019", "extraordinary circumstances strike weather no compensation","en", "customer",
                ["extraordinary_circumstances_en"], ["fraud_detection_thresholds_en"],
                "Extraordinary circumstances coverage"),
    RagTestCase("TC-020", "lost luggage baggage missing claim",                        "en", "customer",
                ["lost_luggage_en"], ["fraud_detection_thresholds_en"],
                "Lost luggage coverage"),
]


# ---------------------------------------------------------------------------
# Evaluate a single test case
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    id: str
    description: str
    query: str
    user_role: str
    passed: bool
    relevance_hit: bool
    access_control_passed: bool
    latency_ms: float
    retrieved_ids: list[str]
    expected_doc_ids: list[str]
    forbidden_doc_ids: list[str]
    forbidden_found: list[str]
    run_id: str | None = None
    error: str | None = None


def _evaluate_case(tc: RagTestCase, top_k: int = 5) -> TestResult:
    t0 = time.perf_counter()
    retrieved_ids: list[str] = []
    error = None

    try:
        result = search_rag(tc.query, language=tc.language, top_k=top_k, user_role=tc.user_role)
        for doc in result.get("documents", []):
            doc_id = doc.get("id") or doc.get("metadata", {}).get("id", "")
            if doc_id:
                retrieved_ids.append(doc_id)
    except Exception as exc:
        error = str(exc)

    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    relevance_hit = (
        any(eid in retrieved_ids for eid in tc.expected_doc_ids)
        if tc.expected_doc_ids else True
    )
    forbidden_found = [fid for fid in tc.forbidden_doc_ids if fid in retrieved_ids]
    access_control_passed = len(forbidden_found) == 0
    passed = relevance_hit and access_control_passed and error is None

    return TestResult(
        id=tc.id,
        description=tc.description,
        query=tc.query,
        user_role=tc.user_role,
        passed=passed,
        relevance_hit=relevance_hit,
        access_control_passed=access_control_passed,
        latency_ms=latency_ms,
        retrieved_ids=retrieved_ids,
        expected_doc_ids=tc.expected_doc_ids,
        forbidden_doc_ids=tc.forbidden_doc_ids,
        forbidden_found=forbidden_found,
        error=error,
    )


# ---------------------------------------------------------------------------
# LangSmith tracing wrapper
# ---------------------------------------------------------------------------

def _run_with_langsmith(tc: RagTestCase, client, project: str, top_k: int) -> TestResult:
    """Run one test case inside a LangSmith traced run."""
    from langsmith.run_trees import RunTree

    run = RunTree(
        name=f"rag_eval_{tc.id}",
        run_type="chain",
        project_name=project,
        inputs={
            "query": tc.query,
            "language": tc.language,
            "user_role": tc.user_role,
            "expected_doc_ids": tc.expected_doc_ids,
        },
    )
    run.post()

    result = _evaluate_case(tc, top_k=top_k)
    result.run_id = str(run.id)

    run.end(outputs={
        "passed": result.passed,
        "retrieved_ids": result.retrieved_ids,
        "relevance_hit": result.relevance_hit,
        "access_control_passed": result.access_control_passed,
        "latency_ms": result.latency_ms,
        "forbidden_found": result.forbidden_found,
        "error": result.error,
    })
    run.patch()

    # Push metric scores as LangSmith feedback
    scores = {
        "relevance_hit":         1.0 if result.relevance_hit else 0.0,
        "access_control_passed": 1.0 if result.access_control_passed else 0.0,
        "passed":                1.0 if result.passed else 0.0,
        "latency_ms":            result.latency_ms,
    }
    for key, value in scores.items():
        try:
            client.create_feedback(
                run_id=run.id,
                key=key,
                score=value,
                source_info={"evaluator": "debian_rag_eval"},
            )
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------

def run_langsmith_rag_eval(top_k: int = 5) -> dict:
    """
    Run the full RAG evaluation suite with LangSmith tracing.

    - If LANGSMITH_API_KEY is set: traces appear in LangSmith UI.
    - Always prints results to the terminal.
    - Always writes results to runtime_logs/evaluation_events.jsonl.
    """
    client = _get_langsmith_client()
    project = get_env("LANGSMITH_PROJECT", "debian-rag-eval")

    if client:
        _ensure_project(client, project)
        print(f"[LangSmith] Tracing to project: {project}")
    else:
        print("[LangSmith] No API key — running locally without tracing.")

    results: list[TestResult] = []

    for tc in RAG_TEST_CASES:
        if client:
            result = _run_with_langsmith(tc, client, project, top_k)
        else:
            result = _evaluate_case(tc, top_k=top_k)
        results.append(result)

    # Aggregate
    total   = len(results)
    passed  = sum(1 for r in results if r.passed)
    failed  = total - passed

    roles = ["customer", "employee", "admin"]
    by_role: dict[str, dict] = {}
    for role in roles:
        rr = [r for r in results if r.user_role == role]
        rp = sum(1 for r in rr if r.passed)
        by_role[role] = {
            "total": len(rr), "passed": rp, "failed": len(rr) - rp,
            "pass_rate_pct": round(rp / len(rr) * 100, 1) if rr else 0,
        }

    ac_passed  = sum(1 for r in results if r.access_control_passed)
    rel_passed = sum(1 for r in results if r.relevance_hit)
    avg_lat    = round(sum(r.latency_ms for r in results) / total, 1) if total else 0

    report = {
        "suite":                       "debian_rag_langsmith_eval_v1",
        "langsmith_project":           project,
        "top_k":                       top_k,
        "total":                       total,
        "passed":                      passed,
        "failed":                      failed,
        "pass_rate_pct":               round(passed / total * 100, 1),
        "relevance_pass_rate_pct":     round(rel_passed / total * 100, 1),
        "access_control_pass_rate_pct":round(ac_passed / total * 100, 1),
        "avg_latency_ms":              avg_lat,
        "summary_by_role":             by_role,
        "results":                     [asdict(r) for r in results],
        "failures":                    [asdict(r) for r in results if not r.passed],
    }

    write_evaluation_event({"event": "langsmith_rag_eval", **{k: v for k, v in report.items() if k != "results"}})

    return report


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")

    report = run_langsmith_rag_eval(top_k=5)

    print(f"\n{'='*60}")
    print(f"  Suite    : {report['suite']}")
    print(f"  Project  : {report['langsmith_project']}")
    print(f"  Total    : {report['total']}   Passed: {report['passed']}   Failed: {report['failed']}")
    print(f"  Pass Rate            : {report['pass_rate_pct']}%")
    print(f"  Relevance Pass Rate  : {report['relevance_pass_rate_pct']}%")
    print(f"  Access Control Rate  : {report['access_control_pass_rate_pct']}%")
    print(f"  Avg Latency          : {report['avg_latency_ms']} ms")
    print(f"{'='*60}\n")

    print("Per-role breakdown:")
    for role, stats in report["summary_by_role"].items():
        icon = "✅" if stats["failed"] == 0 else "❌"
        print(f"  {icon} {role:10s}  {stats['passed']}/{stats['total']} passed ({stats['pass_rate_pct']}%)")

    print()
    if report["failures"]:
        print(f"FAILURES ({len(report['failures'])}):")
        for f in report["failures"]:
            print(f"  ❌ [{f['id']}] {f['description']}")
            if f["forbidden_found"]:
                print(f"       Leaked: {f['forbidden_found']}")
            if not f["relevance_hit"]:
                print(f"       Expected one of: {f['expected_doc_ids']}")
                print(f"       Got: {f['retrieved_ids']}")
    else:
        print("✅ All tests passed!")

    if report.get("langsmith_project"):
        print(f"\n🔗 View traces: https://smith.langchain.com/projects/{report['langsmith_project']}")
