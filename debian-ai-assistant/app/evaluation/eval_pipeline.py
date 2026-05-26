"""
Evaluation service.

Metrics:
- PII leakage
- intent accuracy
- groundedness (RAG-grounded, replaces placeholder)
- tool-call accuracy
- latency placeholder
- RAG-specific: precision, recall, MRR, context utilisation,
  groundedness, faithfulness, answer relevance
"""

from __future__ import annotations

from app.security.governance import write_evaluation_event
from app.tools.pii_masking_tool import contains_iban_like_text
from app.evaluation.rag_eval import evaluate_rag


def evaluate_response(user_message: str, assistant_response: dict, expected_intent: str | None = None) -> dict:
    response_text = str(assistant_response)
    pii_leak_detected = contains_iban_like_text(response_text)
    intent = assistant_response.get("intent")
    answer = assistant_response.get("response", response_text)
    rag_context = assistant_response.get("rag_context", {})

    # Run RAG evaluation when context is present
    rag_metrics: dict = {}
    if rag_context.get("documents"):
        rag_metrics = evaluate_rag(
            question=user_message,
            answer=answer,
            rag_context=rag_context,
            write_event=False,  # parent call writes the combined event below
        )

    result = {
        "pii_leak_detected": pii_leak_detected,
        "intent": intent,
        "expected_intent": expected_intent,
        "tool_call_accuracy": None if expected_intent is None else intent == expected_intent,
        # Groundedness now comes from the real RAG evaluator when available
        "groundedness_score": rag_metrics.get("groundedness_score", 0.45),
        "basic_quality_score": 0 if pii_leak_detected else 1,
        "rag_metrics": rag_metrics,
    }

    write_evaluation_event(
        {
            "user_message": user_message,
            "assistant_response": assistant_response,
            "evaluation": result,
        }
    )

    return result


def run_eval_suite() -> dict:
    test_cases = [
        {
            "user_message": "I want compensation for delayed train",
            "expected_intent": "compensation_guidance",
        },
        {
            "user_message": "I need human support",
            "expected_intent": "human_handoff",
        },
    ]

    return {
        "suite": "debian_basic_eval_suite",
        "test_cases": test_cases,
        "note": "Run-time evaluation is also executed inside agent responses.",
    }


def run_rag_eval_suite_default() -> dict:
    """
    Run the built-in RAG evaluation suite against the live retriever.

    Each test case specifies:
      - question      the query sent to the RAG pipeline
      - gold_ids      document IDs that *must* appear in the retrieved set
                      (leave empty when unknown; recall defaults to 1.0)

    Returns the aggregated metrics dict produced by
    ``app.evaluation.rag_eval.run_rag_eval_suite``.
    """
    from app.rag.retriever import search_rag
    from app.evaluation.rag_eval import run_rag_eval_suite

    test_cases = [
        {
            "question": "How much compensation am I entitled to for a 90-minute train delay?",
            "gold_ids": ["passenger_rights_en"],
        },
        {
            "question": "What refund methods are available for cancelled tickets?",
            "gold_ids": ["refund_methods_en"],
        },
        {
            "question": "Where can I find help at the station?",
            "gold_ids": ["station_faq_en"],
        },
        {
            "question": "Wie beantrage ich eine Entschädigung für Zugverspätung?",
            "gold_ids": ["passenger_rights_de"],
        },
        {
            "question": "What are the escalation steps for a high-occupancy situation?",
            "gold_ids": [],
        },
    ]

    def retrieve_fn(question: str) -> dict:
        return search_rag(question, top_k=5)

    def generate_fn(question: str, rag_context: dict) -> str:
        # Stub: concatenate retrieved doc texts as a stand-in for LLM generation.
        # Replace with your real LLM call (openai_client.chat_completion etc.)
        docs = rag_context.get("documents", [])
        snippets = [
            d.get("metadata", {}).get("text") or d.get("text", "")
            for d in docs
        ]
        return " ".join(filter(None, snippets))

    return run_rag_eval_suite(test_cases, retrieve_fn, generate_fn)
