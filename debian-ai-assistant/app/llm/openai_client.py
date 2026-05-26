"""
LLM client — powered by LangChain 1.x.

Uses:
  - ChatOpenAI              (LLM)
  - ChatPromptTemplate      (prompt assembly)
  - LCEL chain              (prompt | llm | parser)
  - HumanMessage/AIMessage  (conversation history, no memory class needed)
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser

from app.config import get_env
from app.llm.prompt_builder import SYSTEM_PROMPT, build_llm_input
from app.tools.pii_masking_tool import mask_pii_text


def llm_status() -> dict:
    return {
        "provider": "openai_via_langchain",
        "configured": bool(get_env("OPENAI_API_KEY")),
        "model": get_env("OPENAI_MODEL", "gpt-4.1-mini"),
        "mode": "langchain_chat" if get_env("OPENAI_API_KEY") else "local_fallback",
    }


def generate_llm_response(
    user_message: str,
    intent: str,
    language: str,
    rag_context: dict,
    tool_result: dict,
    fallback_response: str,
    history: list | None = None,
) -> dict:
    if not get_env("OPENAI_API_KEY", ""):
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

    # Build history as LangChain message objects (no memory class needed in 1.x)
    chat_history = []
    for turn in (history or [])[-8:]:
        role = turn.get("role", "")
        content = mask_pii_text(str(turn.get("content", "")))
        if role == "user":
            chat_history.append(HumanMessage(content=content))
        elif role == "assistant":
            chat_history.append(AIMessage(content=content))

    llm = ChatOpenAI(
        model=get_env("OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0.2,
        max_tokens=450,
        api_key=get_env("OPENAI_API_KEY"),
    )

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{user_input}"),
    ])

    chain = prompt | llm | StrOutputParser()

    try:
        text = chain.invoke({"user_input": user_input, "history": chat_history})
        return {
            "text": mask_pii_text(text),
            "used_llm": True,
            "llm_status": llm_status(),
        }
    except Exception as error:
        return {
            "text": fallback_response,
            "used_llm": False,
            "llm_status": llm_status(),
            "reason": str(error),
        }
