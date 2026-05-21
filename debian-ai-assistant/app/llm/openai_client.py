"""
OpenAI LLM client using Python standard library only.

The app still works without OPENAI_API_KEY.
If OPENAI_API_KEY is missing or the API call fails, DeBian uses the fallback response.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.config import get_env
from app.llm.prompt_builder import SYSTEM_PROMPT, build_llm_input
from app.tools.pii_masking_tool import mask_pii_text


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def llm_status() -> dict:
    return {
        "provider": "openai",
        "configured": bool(get_env("OPENAI_API_KEY")),
        "model": get_env("OPENAI_MODEL", "gpt-4.1-mini"),
        "mode": "openai_responses_api" if get_env("OPENAI_API_KEY") else "local_fallback",
    }


def generate_llm_response(
    user_message: str,
    intent: str,
    language: str,
    rag_context: dict,
    tool_result: dict,
    fallback_response: str,
) -> dict:
    api_key = get_env("OPENAI_API_KEY", "")
    model = get_env("OPENAI_MODEL", "gpt-4.1-mini")

    if not api_key:
        return {
            "text": fallback_response,
            "used_llm": False,
            "llm_status": llm_status(),
            "reason": "OPENAI_API_KEY is not configured.",
        }

    user_input = build_llm_input(
        user_message=user_message,
        intent=intent,
        language=language,
        rag_context=rag_context,
        tool_result=tool_result,
        fallback_response=fallback_response,
    )

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
        "temperature": 0.2,
        "max_output_tokens": 450,
    }

    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        text = _extract_output_text(data) or fallback_response
        return {
            "text": mask_pii_text(text),
            "used_llm": True,
            "llm_status": llm_status(),
        }

    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="ignore")
        return {
            "text": fallback_response,
            "used_llm": False,
            "llm_status": llm_status(),
            "reason": f"OpenAI HTTP error {error.code}: {body[:300]}",
        }

    except Exception as error:
        return {
            "text": fallback_response,
            "used_llm": False,
            "llm_status": llm_status(),
            "reason": str(error),
        }


def _extract_output_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]

    texts = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                texts.append(content["text"])

    return "\n".join(texts).strip()
