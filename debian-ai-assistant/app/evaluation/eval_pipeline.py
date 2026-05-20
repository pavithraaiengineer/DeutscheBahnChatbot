"""
Evaluation pipeline.

Production metrics:
- groundedness
- relevance
- tool-call accuracy
- PII leakage
- multilingual quality
- latency
"""

from __future__ import annotations

from app.tools.pii_masking_tool import contains_iban_like_text
from app.security.governance import write_evaluation_event


def evaluate_response(user_message: str, assistant_response: dict, expected_intent: str | None = None) -> dict:
    response_text = str(assistant_response)

    pii_leak_detected = contains_iban_like_text(response_text)
    intent = assistant_response.get("intent")

    result = {
        "pii_leak_detected": pii_leak_detected,
        "intent": intent,
        "expected_intent": expected_intent,
        "tool_call_accuracy": None if expected_intent is None else intent == expected_intent,
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
