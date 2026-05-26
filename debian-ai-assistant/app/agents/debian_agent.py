"""
DeBian agent — powered by LangChain.

Uses the LangChain 1.x API:
  - create_agent  (replaces create_tool_calling_agent from 0.x)
  - @tool decorator for tool definitions
  - Falls back to keyword-based routing when no API key is set.

The public interface (DebianAgent.respond) is unchanged.
"""

from __future__ import annotations

from app.config import get_env
from app.evaluation.eval_pipeline import evaluate_response
from app.llm.prompt_builder import SYSTEM_PROMPT
from app.rag.retriever import retrieve_context
from app.rag.query_optimizer import detect_language
from app.security.governance import write_analytics_event, write_audit_event, sanitize_payload
from app.security.guardrails import InputGuardrail, OutputGuardrail
from app.tools.compensation_tool import submit_compensation_claim
from app.tools.delay_tool import get_delay_status
from app.tools.human_handoff_tool import request_human_handoff
from app.tools.pii_masking_tool import mask_pii_text
from app.tools.route_tool import get_alternative_routes


# ---------------------------------------------------------------------------
# Intent keyword fallback (used when OPENAI_API_KEY is absent)
# ---------------------------------------------------------------------------

_DELAY_WORDS = [
    "delay","delayed","late","verspätung","verspätet","retard","retardé",
    "retraso","retrasado","ritardo","gecikme","opóźnienie","تأخير","தாமதம்",
]
_COMPENSATION_WORDS = [
    "refund","compensation","claim","voucher","reimburse",
    "erstattung","entschädigung","gutschein","remboursement","indemnisation",
    "reembolso","compensación","rimborso","indennizzo","geri ödeme","tazminat",
    "zwrot","odszkodowanie","استرداد","تعويض","பணம்",
]
_ROUTE_WORDS = [
    "route","alternative","connection","verbindung","ersatz","alternativ",
    "itinéraire","alternatif","ruta","alternativa","percorso","güzergah","trasa",
    "مسار","வழி",
]
_HUMAN_WORDS = [
    "human","agent","person","help","support","speak","talk","operator",
    "mensch","hilfe","sprechen","aide","humain","ayuda","humano",
    "aiuto","umano","yardım","pomoc","człowiek","إنسان","மனித",
]


def _keyword_intent(message: str) -> str:
    low = message.lower()
    if any(w in low for w in _HUMAN_WORDS):
        return "human_handoff"
    if any(w in low for w in _COMPENSATION_WORDS):
        return "compensation_guidance"
    if any(w in low for w in _DELAY_WORDS):
        return "delay_lookup"
    if any(w in low for w in _ROUTE_WORDS):
        return "route_alternatives"
    return "general"


# ---------------------------------------------------------------------------
# LangChain tools (built per-request so payload/role are in closure scope)
# ---------------------------------------------------------------------------

def _make_tools(payload: dict, user_role: str, language: str):
    from langchain_core.tools import tool

    @tool
    def delay_lookup(train_number: str) -> str:
        """Check real-time train delay status. Input: train number e.g. ICE 999."""
        result = get_delay_status({"train_number": train_number, **payload})
        return str(result)

    @tool
    def compensation_claim(details: str) -> str:
        """Submit a passenger compensation claim. Input: claim details as text."""
        result = submit_compensation_claim({**payload, "details": details})
        return str(result)

    @tool
    def route_alternatives(query: str) -> str:
        """Find alternative routes when a train is cancelled or severely delayed."""
        result = get_alternative_routes({**payload, "query": query})
        return str(result)

    @tool
    def human_handoff(reason: str) -> str:
        """Escalate to a human agent. Input: reason for escalation."""
        result = request_human_handoff({
            "language": language,
            "reason": reason,
            "priority": payload.get("priority", "normal"),
        })
        return str(result)

    @tool
    def rag_search(query: str) -> str:
        """Search the knowledge base for policy, passenger rights, or FAQ information."""
        ctx = retrieve_context(query, user_role=user_role)
        docs = ctx.get("documents", [])
        texts = [d.get("metadata", {}).get("text", "") for d in docs]
        return "\n\n".join(filter(None, texts)) or "No relevant documents found."

    return [delay_lookup, compensation_claim, route_alternatives, human_handoff, rag_search]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class DeBianAgent:
    def __init__(self) -> None:
        pass

    def classify_intent(self, message: str, payload: dict | None = None) -> str:
        return _keyword_intent(message)

    def respond(
        self,
        message: str,
        payload: dict | None = None,
        history: list | None = None,
        user_role: str = "customer",
    ) -> dict:
        payload = payload or {}
        language = payload.get("language") or detect_language(message)
        intent = self.classify_intent(message, payload)
        session_id = payload.get("session_id", "anonymous")

        # ── INPUT GUARDRAIL ───────────────────────────────────────────────
        input_check = InputGuardrail.check(
            message=message, user_role=user_role,
            session_id=session_id, language=language,
        )
        if input_check.blocked:
            return input_check.error_response(language)

        # ── RAG CONTEXT ───────────────────────────────────────────────────
        rag_context = retrieve_context(mask_pii_text(message), language=language, user_role=user_role)

        # ── LANGCHAIN AGENT ───────────────────────────────────────────────
        api_key = get_env("OPENAI_API_KEY", "")
        selected_tool = None
        tool_result: dict = {}
        used_llm = False
        llm_status_info: dict = {"provider": "langchain", "configured": bool(api_key)}

        if api_key:
            try:
                from langchain.agents import create_agent
                from langchain_openai import ChatOpenAI
                from langchain_core.messages import HumanMessage, AIMessage

                tools = _make_tools(payload, user_role, language)

                llm = ChatOpenAI(
                    model=get_env("OPENAI_MODEL", "gpt-4.1-mini"),
                    temperature=0.2,
                    max_tokens=450,
                    api_key=api_key,
                )

                agent = create_agent(
                    model=llm,
                    tools=tools,
                    system_prompt=SYSTEM_PROMPT,
                )

                # Build chat history
                chat_history = []
                for turn in (history or [])[-8:]:
                    role = turn.get("role", "")
                    content = mask_pii_text(str(turn.get("content", "")))
                    if role == "user":
                        chat_history.append(HumanMessage(content=content))
                    elif role == "assistant":
                        chat_history.append(AIMessage(content=content))

                result = agent.invoke(
                    {"messages": chat_history + [HumanMessage(content=f"[Language: {language}] {mask_pii_text(message)}")]}
                )

                # LangChain 1.x returns messages list
                messages = result.get("messages", [])
                raw_text = messages[-1].content if messages else self._build_fallback_response(intent, language, None)
                used_llm = True
                llm_status_info["mode"] = "langchain_agent"

            except Exception as err:
                raw_text = self._build_fallback_response(intent, language, None)
                llm_status_info["reason"] = str(err)
                llm_status_info["mode"] = "fallback_after_error"
        else:
            # No API key — keyword-route to tools directly
            if intent == "delay_lookup" and payload.get("train_number"):
                selected_tool = "delay_lookup"
                tool_result = get_delay_status(payload)
            elif intent == "compensation_claim":
                selected_tool = "compensation_claim"
                tool_result = submit_compensation_claim(payload)
            elif intent == "route_alternatives":
                selected_tool = "route_alternatives"
                tool_result = get_alternative_routes(payload)
            elif intent == "human_handoff":
                selected_tool = "human_handoff"
                tool_result = request_human_handoff({
                    "language": language,
                    "reason": message,
                    "priority": payload.get("priority", "normal"),
                })
            raw_text = self._build_fallback_response(intent, language, tool_result or None)
            llm_status_info["mode"] = "local_fallback"

        # ── OUTPUT GUARDRAIL ──────────────────────────────────────────────
        output_check = OutputGuardrail.check(
            llm_text=raw_text, user_role=user_role,
            language=language, session_id=session_id,
        )
        safe_response_text = mask_pii_text(output_check.safe_text)

        response = {
            "assistant": "DeBian",
            "language": language,
            "intent": intent,
            "selected_tool": selected_tool,
            "response": safe_response_text,
            "used_llm": used_llm,
            "llm_status": llm_status_info,
            "tool_result": sanitize_payload(tool_result),
            "rag_context": rag_context,
            "guardrail_output_redacted": output_check.redacted,
            "flow": [
                "User input received by text, voice, or image",
                "Backend receives request",
                "Language detected",
                "Voice/image placeholder handled if uploaded",
                "Agent classifies intent",
                "LangChain agent selects and calls tools",
                "Delay/compensation/RAG data retrieved",
                "PII masked",
                "Response streamed/returned",
                "Analytics written for BigQuery-style reporting",
                "Evaluation logs stored for quality improvement",
            ],
        }

        write_analytics_event("agent_response", {
            "session_id": session_id,
            "intent": intent,
            "language": language,
            "used_llm": used_llm,
        })
        write_audit_event(
            actor=user_role,
            action="agent_respond",
            resource="debian_agent",
            payload={"intent": intent, "session_id": session_id},
        )
        evaluate_response(
            user_message=message,
            assistant_response=response,
            expected_intent=None,
        )

        return response

    def _build_fallback_response(self, intent: str, language: str, tool_result: dict | None) -> str:
        defaults = {
            "en": {
                "general": "Hello, I am DeBian. Please choose Book a ticket, Claim compensation, Check delay, or Human assistance.",
                "delay_lookup": "I have retrieved the delay information for your train.",
                "compensation_guidance": "I can help you claim compensation for your delayed train.",
                "route_alternatives": "Here are alternative routes available for your journey.",
                "human_handoff": "Connecting you to a human agent now.",
            },
            "de": {
                "general": "Hallo, ich bin DeBian. Bitte wählen Sie: Ticket buchen, Entschädigung beantragen, Verspätung prüfen oder menschliche Hilfe.",
                "delay_lookup": "Ich habe die Verspätungsinformationen für Ihren Zug abgerufen.",
                "compensation_guidance": "Ich kann Ihnen helfen, eine Entschädigung zu beantragen.",
                "route_alternatives": "Hier sind alternative Verbindungen für Ihre Reise.",
                "human_handoff": "Sie werden jetzt mit einem Mitarbeiter verbunden.",
            },
        }
        lang_map = defaults.get(language, defaults["en"])
        return lang_map.get(intent, lang_map["general"])
