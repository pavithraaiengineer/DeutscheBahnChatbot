"""
Evaluation service.

Metrics:
- PII leakage
- intent accuracy
- groundedness placeholder
- tool-call accuracy
- latency placeholder
"""

from __future__ import annotations

from app.security.governance import write_evaluation_event
from app.tools.pii_masking_tool import contains_iban_like_text


def evaluate_response(user_message: str, assistant_response: dict, expected_intent: str | None = None) -> dict:
    response_text = str(assistant_response)
    pii_leak_detected = contains_iban_like_text(response_text)
    intent = assistant_response.get("intent")

    result = {
        "pii_leak_detected": pii_leak_detected,
        "intent": intent,
        "expected_intent": expected_intent,
        "tool_call_accuracy": None if expected_intent is None else intent == expected_intent,
        "groundedness_score": 0.85 if assistant_response.get("rag_context", {}).get("documents") else 0.45,
        "basic_quality_score": 0 if pii_leak_detected else 1,
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
