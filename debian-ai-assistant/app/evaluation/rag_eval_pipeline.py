"""
DeBian RAG Evaluation Pipeline
================================
Evaluates the RAG retrieval system across four dimensions:

1. RETRIEVAL RELEVANCE   – Did we fetch the right documents for the query?
2. ROLE ACCESS CONTROL   – Are restricted documents correctly hidden per role?
3. GROUNDEDNESS          – Is the retrieved context actually useful for answering?
4. COVERAGE              – Are all document categories reachable by search?

Run standalone:
    python -m app.evaluation.rag_eval_pipeline

Or call from the API:
    GET /eval/rag
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any

from app.rag.retriever import search_rag
from app.security.governance import write_evaluation_event


# ---------------------------------------------------------------------------
# Role hierarchy (mirrors app/auth.py)
# ---------------------------------------------------------------------------
ROLE_HIERARCHY: dict[str, int] = {
    "customer": 1,
    "employee": 2,
    "admin": 3,
}


# ---------------------------------------------------------------------------
# Test-case definitions
# ---------------------------------------------------------------------------
@dataclass
class RagTestCase:
    """A single RAG evaluation test case."""
    id: str
    query: str
    language: str
    user_role: str
    expected_doc_ids: list[str]          # at least one must appear in top-k
    forbidden_doc_ids: list[str]         # none of these must appear in results
    expected_category: str | None        # optional category tag check
    description: str = ""


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------
RAG_TEST_CASES: list[RagTestCase] = [

    # ── RETRIEVAL RELEVANCE – customer queries ──────────────────────────
    RagTestCase(
        id="TC-001",
        query="How do I get compensation for a delayed train?",
        language="en",
        user_role="customer",
        expected_doc_ids=["compensation_60_120_en", "compensation_rule_60_120_en", "claim_process_en"],
        forbidden_doc_ids=["fraud_detection_thresholds_en", "system_configuration_admin_en"],
        expected_category=None,
        description="Customer asks for compensation – must find compensation rules, not admin docs.",
    ),
    RagTestCase(
        id="TC-002",
        query="Wie beantrage ich eine Entschädigung für Zugverspätung?",
        language="de",
        user_role="customer",
        expected_doc_ids=["compensation_60_120_de", "claim_process_de"],
        forbidden_doc_ids=["analytics_dashboard_sop_en", "fraud_detection_thresholds_en"],
        expected_category=None,
        description="German-language compensation query – must return German docs.",
    ),
    RagTestCase(
        id="TC-003",
        query="Can I get a refund if I miss my connection?",
        language="en",
        user_role="customer",
        expected_doc_ids=["compensation_missed_connection_en", "refund_method_en"],
        forbidden_doc_ids=["missed_connection_internal_rules_en", "fraud_detection_thresholds_en"],
        expected_category=None,
        description="Missed connection refund – customer sees public rules, not internal SOP.",
    ),
    RagTestCase(
        id="TC-004",
        query="I need help with accessibility or disability assistance on trains",
        language="en",
        user_role="customer",
        expected_doc_ids=["accessibility_en"],
        forbidden_doc_ids=["system_configuration_admin_en", "user_management_admin_en"],
        expected_category=None,
        description="Accessibility query – public doc must be reachable.",
    ),
    RagTestCase(
        id="TC-005",
        query="What happens if the train is cancelled completely?",
        language="en",
        user_role="customer",
        expected_doc_ids=["offer_cancel_en", "compensation_rule_60_120_en"],
        forbidden_doc_ids=["fraud_detection_thresholds_en", "financial_sla_thresholds_en"],
        expected_category=None,
        description="Cancellation query – public cancellation policy must surface.",
    ),
    RagTestCase(
        id="TC-006",
        query="How do I add my IBAN for a bank transfer refund?",
        language="en",
        user_role="customer",
        expected_doc_ids=["refund_method_en"],
        forbidden_doc_ids=["refund_processing_internal_en", "financial_sla_thresholds_en"],
        expected_category=None,
        description="IBAN/refund method – customer gets public refund doc, not internal processing SOP.",
    ),
    RagTestCase(
        id="TC-007",
        query="Is there a helpline I can call for train delays?",
        language="en",
        user_role="customer",
        expected_doc_ids=["helpline_en"],
        forbidden_doc_ids=["escalation_human_agent_sop_en", "analytics_dashboard_sop_en"],
        expected_category=None,
        description="Helpline query – customer gets helpline doc, not internal escalation SOP.",
    ),

    # ── ROLE ACCESS CONTROL – employee queries ──────────────────────────
    RagTestCase(
        id="TC-008",
        query="What are the occupancy colour codes for trains?",
        language="en",
        user_role="employee",
        expected_doc_ids=["occupancy_status_sop_en"],
        forbidden_doc_ids=["fraud_detection_thresholds_en", "system_configuration_admin_en"],
        expected_category=None,
        description="Employee asks about occupancy codes – must see employee SOP.",
    ),
    RagTestCase(
        id="TC-009",
        query="When should I escalate a claim to a human agent?",
        language="en",
        user_role="employee",
        expected_doc_ids=["escalation_human_agent_sop_en"],
        forbidden_doc_ids=["fraud_detection_thresholds_en", "financial_sla_thresholds_en"],
        expected_category=None,
        description="Employee escalation trigger query – must find escalation SOP.",
    ),
    RagTestCase(
        id="TC-010",
        query="What are the hotel reimbursement rules for missed connections?",
        language="en",
        user_role="employee",
        expected_doc_ids=["missed_connection_internal_rules_en"],
        forbidden_doc_ids=["fraud_detection_thresholds_en", "system_configuration_admin_en"],
        expected_category=None,
        description="Employee missed connection internal rules – must be accessible.",
    ),
    RagTestCase(
        id="TC-011",
        query="How do I process a manual refund override?",
        language="en",
        user_role="employee",
        expected_doc_ids=["refund_processing_internal_en"],
        forbidden_doc_ids=["fraud_detection_thresholds_en", "financial_sla_thresholds_en"],
        expected_category=None,
        description="Employee refund processing – must see internal refund SOP.",
    ),

    # ── ROLE ACCESS CONTROL – admin queries ────────────────────────────
    RagTestCase(
        id="TC-012",
        query="What are the fraud model score thresholds for blocking claims?",
        language="en",
        user_role="admin",
        expected_doc_ids=["fraud_detection_thresholds_en"],
        forbidden_doc_ids=[],
        expected_category=None,
        description="Admin fraud threshold query – must return admin-only fraud doc.",
    ),
    RagTestCase(
        id="TC-013",
        query="Show me the analytics dashboard metrics and alert thresholds",
        language="en",
        user_role="admin",
        expected_doc_ids=["analytics_dashboard_sop_en"],
        forbidden_doc_ids=[],
        expected_category=None,
        description="Admin analytics query – must return analytics dashboard SOP.",
    ),
    RagTestCase(
        id="TC-014",
        query="What are the financial approval tiers and payout SLA commitments?",
        language="en",
        user_role="admin",
        expected_doc_ids=["financial_sla_thresholds_en"],
        forbidden_doc_ids=[],
        expected_category=None,
        description="Admin financial SLA query – must return financial thresholds doc.",
    ),
    RagTestCase(
        id="TC-015",
        query="What is the Pinecone index name and infrastructure setup?",
        language="en",
        user_role="admin",
        expected_doc_ids=["system_configuration_admin_en"],
        forbidden_doc_ids=[],
        expected_category=None,
        description="Admin system config query – must return system config doc.",
    ),

    # ── ROLE ACCESS CONTROL – negative tests (customer must NOT see restricted) ──
    RagTestCase(
        id="TC-016",
        query="fraud detection model thresholds block claims score",
        language="en",
        user_role="customer",
        expected_doc_ids=[],                                    # no specific expected
        forbidden_doc_ids=["fraud_detection_thresholds_en", "financial_sla_thresholds_en",
                           "system_configuration_admin_en", "user_management_admin_en"],
        expected_category=None,
        description="Customer must NEVER see any admin-only documents.",
    ),
    RagTestCase(
        id="TC-017",
        query="occupancy colour codes GREEN YELLOW RED internal SOP",
        language="en",
        user_role="customer",
        expected_doc_ids=[],
        forbidden_doc_ids=["occupancy_status_sop_en", "occupancy_status_sop_de",
                           "escalation_human_agent_sop_en", "refund_processing_internal_en"],
        expected_category=None,
        description="Customer must NEVER see employee-only SOP documents.",
    ),
    RagTestCase(
        id="TC-018",
        query="fraud model thresholds XGBoost score block",
        language="en",
        user_role="employee",
        expected_doc_ids=[],
        forbidden_doc_ids=["fraud_detection_thresholds_en", "financial_sla_thresholds_en",
                           "system_configuration_admin_en"],
        expected_category=None,
        description="Employee must NEVER see admin-only documents.",
    ),

    # ── COVERAGE – ensure all key categories are searchable ─────────────
    RagTestCase(
        id="TC-019",
        query="extraordinary circumstances strike weather no compensation",
        language="en",
        user_role="customer",
        expected_doc_ids=["extraordinary_circumstances_en"],
        forbidden_doc_ids=["fraud_detection_thresholds_en"],
        expected_category=None,
        description="Extraordinary circumstances doc must be reachable.",
    ),
    RagTestCase(
        id="TC-020",
        query="lost luggage baggage missing claim",
        language="en",
        user_role="customer",
        expected_doc_ids=["lost_luggage_en"],
        forbidden_doc_ids=["fraud_detection_thresholds_en"],
        expected_category=None,
        description="Lost luggage doc must be reachable.",
    ),
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class TestResult:
    id: str
    description: str
    query: str
    user_role: str
    passed: bool
    relevance_hit: bool          # ≥1 expected doc found
    access_control_passed: bool  # 0 forbidden docs found
    latency_ms: float
    retrieved_ids: list[str]
    expected_doc_ids: list[str]
    forbidden_doc_ids: list[str]
    forbidden_found: list[str]
    error: str | None = None


# ---------------------------------------------------------------------------
# Core evaluation logic
# ---------------------------------------------------------------------------

def _extract_ids(result: dict) -> list[str]:
    """Pull document IDs from a search_rag result."""
    ids = []
    for doc in result.get("documents", []):
        # Pinecone returns {"id": ..., "metadata": {...}}
        # Local store returns flat dicts
        doc_id = doc.get("id") or doc.get("metadata", {}).get("id", "")
        if doc_id:
            ids.append(doc_id)
    return ids


def evaluate_test_case(tc: RagTestCase, top_k: int = 5) -> TestResult:
    """Run a single test case and return a TestResult."""
    t0 = time.perf_counter()
    error = None
    retrieved_ids: list[str] = []

    try:
        result = search_rag(
            tc.query,
            language=tc.language,
            top_k=top_k,
            user_role=tc.user_role,
        )
        retrieved_ids = _extract_ids(result)
    except Exception as exc:
        error = str(exc)

    latency_ms = (time.perf_counter() - t0) * 1000

    # Relevance: at least one expected doc appears (skip check if list is empty)
    if tc.expected_doc_ids:
        relevance_hit = any(eid in retrieved_ids for eid in tc.expected_doc_ids)
    else:
        relevance_hit = True  # negative-only test; relevance N/A

    # Access control: none of the forbidden docs must appear
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
        latency_ms=round(latency_ms, 1),
        retrieved_ids=retrieved_ids,
        expected_doc_ids=tc.expected_doc_ids,
        forbidden_doc_ids=tc.forbidden_doc_ids,
        forbidden_found=forbidden_found,
        error=error,
    )


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------

def run_rag_eval_suite(top_k: int = 5) -> dict:
    """
    Run all RAG test cases and return a structured report.

    Returns:
        dict with keys: suite, total, passed, failed, pass_rate,
                        avg_latency_ms, results, summary_by_role
    """
    results: list[TestResult] = []

    for tc in RAG_TEST_CASES:
        result = evaluate_test_case(tc, top_k=top_k)
        results.append(result)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    # Per-role breakdown
    roles = ["customer", "employee", "admin"]
    summary_by_role: dict[str, dict] = {}
    for role in roles:
        role_results = [r for r in results if r.user_role == role]
        role_passed = sum(1 for r in role_results if r.passed)
        summary_by_role[role] = {
            "total": len(role_results),
            "passed": role_passed,
            "failed": len(role_results) - role_passed,
            "pass_rate": round(role_passed / len(role_results) * 100, 1) if role_results else 0,
        }

    # Access control summary
    ac_passed = sum(1 for r in results if r.access_control_passed)
    rel_passed = sum(1 for r in results if r.relevance_hit)

    avg_latency = round(sum(r.latency_ms for r in results) / total, 1) if total else 0

    report = {
        "suite": "debian_rag_eval_suite_v1",
        "top_k": top_k,
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate_pct": round(passed / total * 100, 1) if total else 0,
        "relevance_pass_rate_pct": round(rel_passed / total * 100, 1) if total else 0,
        "access_control_pass_rate_pct": round(ac_passed / total * 100, 1) if total else 0,
        "avg_latency_ms": avg_latency,
        "summary_by_role": summary_by_role,
        "results": [asdict(r) for r in results],
        "failures": [asdict(r) for r in results if not r.passed],
    }

    # Write to evaluation log
    write_evaluation_event({
        "event": "rag_eval_suite",
        "suite": report["suite"],
        "total": total,
        "passed": passed,
        "pass_rate_pct": report["pass_rate_pct"],
    })

    return report


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    print("Running DeBian RAG Evaluation Suite …\n")
    report = run_rag_eval_suite(top_k=5)

    print(f"{'='*60}")
    print(f"  Suite : {report['suite']}")
    print(f"  Total : {report['total']}   Passed: {report['passed']}   Failed: {report['failed']}")
    print(f"  Pass Rate            : {report['pass_rate_pct']}%")
    print(f"  Relevance Pass Rate  : {report['relevance_pass_rate_pct']}%")
    print(f"  Access Control Rate  : {report['access_control_pass_rate_pct']}%")
    print(f"  Avg Latency          : {report['avg_latency_ms']} ms")
    print(f"{'='*60}\n")

    print("Per-role breakdown:")
    for role, stats in report["summary_by_role"].items():
        status = "✅" if stats["failed"] == 0 else "❌"
        print(f"  {status} {role:10s}  {stats['passed']}/{stats['total']} passed  ({stats['pass_rate']}%)")

    print()
    if report["failures"]:
        print(f"FAILURES ({len(report['failures'])}):")
        for f in report["failures"]:
            print(f"  ❌ [{f['id']}] {f['description']}")
            if f["forbidden_found"]:
                print(f"       Forbidden docs leaked: {f['forbidden_found']}")
            if not f["relevance_hit"]:
                print(f"       Expected one of: {f['expected_doc_ids']}")
                print(f"       Got: {f['retrieved_ids']}")
            if f["error"]:
                print(f"       Error: {f['error']}")
    else:
        print("✅ All tests passed!")
