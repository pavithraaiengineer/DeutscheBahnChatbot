"""
Prompt builder for DeBian.

The LLM receives only masked/sanitized data and is instructed to answer
conversationally, not by dumping JSON.
"""

from __future__ import annotations

import json

from app.tools.pii_masking_tool import mask_pii_text


SYSTEM_PROMPT = """
You are DeBian, a multilingual digital rail customer-support assistant.

DB Flow:
1. User asks question by voice, image, or text.
2. Backend receives request.
3. Language is detected.
4. Voice is converted to text if needed.
5. Image is analyzed if uploaded.
6. Agent classifies intent.
7. Agent calls the correct MCP-like tool.
8. Delay/compensation data is retrieved.
9. PII is masked.
10. Response streams or returns to the user.
11. Analytics are written for BigQuery-style reporting.
12. Evaluation logs are stored for quality improvement.

Your response rules:
- Do not return raw JSON to the user.
- Use the tool result as source of truth.
- Explain the result in natural customer-support language.
- Keep the answer concise and structured.
- If required information is missing, ask exactly one next question.
- Never expose full account numbers, IBANs, API keys, secrets, or private data.
- If an account number appears, show only the last 4 digits.
- If the data source is mock/demo data, clearly say it is demo data.
- If confidence is low or the situation is complex, suggest human assistance.
"""


def build_llm_input(
    user_message: str,
    intent: str,
    language: str,
    rag_context: dict,
    tool_result: dict,
    fallback_response: str,
) -> str:
    safe_user_message = mask_pii_text(user_message)
    safe_tool_result = mask_pii_text(json.dumps(tool_result or {}, ensure_ascii=False, indent=2))
    safe_rag_context = mask_pii_text(json.dumps(_compact_rag_context(rag_context), ensure_ascii=False, indent=2))

    return f"""
User language: {language}
Detected intent: {intent}

User message:
{safe_user_message}

Tool result:
{safe_tool_result}

Retrieved context:
{safe_rag_context}

Safe fallback answer:
{fallback_response}

Write the final answer to the user.
Important: do not return JSON. Return a friendly, readable answer.
"""


def _compact_rag_context(rag_context: dict) -> dict:
    docs = rag_context.get("documents", []) if isinstance(rag_context, dict) else []
    compact_docs = []

    for doc in docs[:3]:
        metadata = doc.get("metadata", doc)
        compact_docs.append(
            {
                "id": doc.get("id") or metadata.get("id"),
                "score": doc.get("score"),
                "language": metadata.get("language"),
                "document_type": metadata.get("document_type"),
                "source_url": metadata.get("source_url"),
                "text": metadata.get("text", "")[:700],
            }
        )

    return {
        "query": rag_context.get("query"),
        "vector_store_mode": rag_context.get("vector_store_mode"),
        "documents": compact_docs,
    }
