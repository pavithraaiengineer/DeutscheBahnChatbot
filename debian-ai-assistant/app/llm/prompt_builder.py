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
- CRITICAL: Always reply in the exact language specified in the "User language" field below.
  Supported languages: English (en), German (de), French (fr), Spanish (es), Italian (it),
  Turkish (tr), Polish (pl), Arabic (ar), Tamil (ta). Do not mix languages.
- Do not return raw JSON to the user.
- CRITICAL: The "Retrieved context" section below is the ONLY authoritative source for this
  conversation. If the retrieved documents contain the answer, use ONLY that information.
  Do NOT answer from general knowledge when retrieved documents cover the topic.
- If retrieved context contains internal operational data (budgets, KPIs, SLA thresholds,
  SOPs, fraud rules, escalation matrices, analytics), present it directly and clearly —
  it has already been access-filtered for this user's role.
- Use the tool result as source of truth for real-time data (delays, occupancy).
- Explain the result in natural customer-support language.
- Keep the answer concise and structured.
- If the answer is NOT in retrieved context or tool result, say you don't have that
  information and offer to connect to a human agent. Do NOT invent answers.
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

    # Map ISO code to full language name so the LLM has an unambiguous instruction.
    lang_names = {
        "en": "English", "de": "German", "fr": "French", "es": "Spanish",
        "it": "Italian", "tr": "Turkish", "pl": "Polish", "ar": "Arabic", "ta": "Tamil",
    }
    lang_label = lang_names.get(language, language)

    return f"""
User language: {language} ({lang_label}) — YOU MUST REPLY ENTIRELY IN {lang_label.upper()}.
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
Important: do not return JSON. Return a friendly, readable answer in {lang_label}.
"""


def _compact_rag_context(rag_context: dict) -> dict:
    docs = rag_context.get("documents", []) if isinstance(rag_context, dict) else []
    compact_docs = []

    for doc in docs[:3]:
        metadata = doc.get("metadata", doc)
        compact_docs.append(
            {
                "id":            doc.get("id") or metadata.get("id"),
                "score":         doc.get("score"),
                "language":      metadata.get("language"),
                "document_type": metadata.get("document_type"),
                "source_url":    metadata.get("source_url"),
                "text":          metadata.get("text", "")[:700],
            }
        )

    return {
        "query":             rag_context.get("query"),
        "vector_store_mode": rag_context.get("vector_store_mode"),
        "documents":         compact_docs,
    }
