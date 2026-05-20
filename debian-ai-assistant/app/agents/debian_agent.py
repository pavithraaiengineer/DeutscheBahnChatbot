"""
DeBian agent.

This is a dependency-light, LangChain-style orchestration:
1. classify intent
2. optimize query
3. retrieve context
4. call the correct tool
5. mask PII
6. write analytics and evaluation logs

Production replacement:
- LangChain / LangGraph graph
- MCP tool server
- streaming LLM responses
"""

from __future__ import annotations

from app.evaluation.eval_pipeline import evaluate_response
from app.rag.retriever import retrieve_context
from app.rag.query_optimizer import detect_language
from app.security.governance import write_analytics_event, sanitize_payload
from app.tools.compensation_tool import submit_compensation_claim
from app.tools.delay_tool import get_delay_status
from app.tools.human_handoff_tool import request_human_handoff
from app.tools.pii_masking_tool import mask_pii_text
from app.tools.route_tool import get_alternative_routes


class MCPToolRegistry:
    """
    MCP-like tool registry for the MVP.

    In production, these functions can be exposed via an actual MCP server.
    """

    def call(self, tool_name: str, payload: dict) -> dict:
        if tool_name == "delay_lookup":
            return get_delay_status(payload.get("train_number", ""))
        if tool_name == "compensation_claim":
            return submit_compensation_claim(payload)
        if tool_name == "route_alternatives":
            return get_alternative_routes(payload.get("origin", ""), payload.get("destination", ""))
        if tool_name == "human_handoff":
            return request_human_handoff(payload.get("language", "en"), payload.get("reason", "customer requested support"))

        raise ValueError(f"Unknown tool: {tool_name}")


class DeBianAgent:
    def __init__(self) -> None:
        self.tools = MCPToolRegistry()

    def classify_intent(self, message: str, payload: dict | None = None) -> str:
        payload = payload or {}
        text = (message or "").lower()

        if payload.get("request_human_assistance"):
            return "human_handoff"
        if payload.get("claim_form"):
            return "compensation_claim"
        if any(word in text for word in ["delay", "delayed", "late", "verspätung", "zug verspätet"]):
            return "delay_lookup"
        if any(word in text for word in ["refund", "compensation", "claim", "erstattung", "entschädigung", "gutschein"]):
            return "compensation_guidance"
        if any(word in text for word in ["route", "alternative", "connection", "verbindung", "ersatz"]):
            return "route_alternatives"
        if any(word in text for word in ["human", "agent", "call", "mitarbeiter", "anrufen", "help"]):
            return "human_handoff"
        if payload.get("image_uploaded"):
            return "image_understanding"
        if payload.get("voice_uploaded"):
            return "voice_processing"

        return "general"

    def respond(self, message: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        language = payload.get("language") or detect_language(message)
        intent = self.classify_intent(message, payload)

        rag_context = retrieve_context(message, language=language)

        tool_result = None
        if intent == "delay_lookup" and payload.get("train_number"):
            tool_result = self.tools.call("delay_lookup", payload)

        elif intent == "compensation_claim":
            tool_result = self.tools.call("compensation_claim", payload)

        elif intent == "route_alternatives":
            tool_result = self.tools.call("route_alternatives", payload)

        elif intent == "human_handoff":
            tool_result = self.tools.call("human_handoff", {"language": language, "reason": message})

        response_text = self._build_response_text(intent, language, tool_result)

        response = {
            "assistant": "DeBian",
            "language": language,
            "intent": intent,
            "response": mask_pii_text(response_text),
            "tool_result": sanitize_payload(tool_result or {}),
            "rag_context": rag_context,
            "flow": [
                "1. User input received by text, voice, or image",
                "2. Request received by backend service",
                "3. Language detected",
                "4. Voice/image placeholder processed if uploaded",
                "5. Agent classified intent",
                "6. MCP-like tool selected",
                "7. Data retrieved from mock operational layer",
                "8. PII masked",
                "9. Response returned to user",
                "10. Analytics written to local JSONL; production writes to BigQuery",
                "11. Evaluation logs stored for quality improvement",
            ],
        }

        write_analytics_event(
            "assistant_response",
            {
                "message": message,
                "language": language,
                "intent": intent,
                "tool_result": tool_result or {},
            },
        )

        response["evaluation"] = evaluate_response(message, response)
        return response

    def _build_response_text(self, intent: str, language: str, tool_result: dict | None) -> str:
        if language == "de":
            if intent == "delay_lookup" and tool_result:
                return f"Der Zugstatus wurde geprüft: {tool_result}"
            if intent == "compensation_claim" and tool_result:
                return "Ihre Entschädigungsanfrage wurde erstellt. Kontodaten werden nur maskiert angezeigt."
            if intent == "compensation_guidance":
                return "Ich kann Ihren Entschädigungsanspruch prüfen. Bitte geben Sie Zugnummer, Verspätung, Ticketpreis und Erstattungsmethode an."
            if intent == "route_alternatives" and tool_result:
                return f"Ich habe alternative Reisemöglichkeiten gefunden: {tool_result}"
            if intent == "human_handoff" and tool_result:
                return "Ich habe eine Anfrage für menschliche Unterstützung erstellt."
            if intent == "image_understanding":
                return "Bildanalyse ist im MVP vorbereitet. In Produktion wird dies mit Vision API oder Gemini Vision verbunden."
            if intent == "voice_processing":
                return "Voice-Verarbeitung ist im MVP vorbereitet. In Produktion wird dies mit Speech-to-Text verbunden."
            return "Hallo, ich bin DeBian. Wie kann ich Ihnen helfen?"

        if intent == "delay_lookup" and tool_result:
            return f"Train status checked: {tool_result}"
        if intent == "compensation_claim" and tool_result:
            return "Your compensation claim has been created. Account details are shown only in masked form."
        if intent == "compensation_guidance":
            return "I can check your compensation eligibility. Please provide train number, delay minutes, ticket price, and refund method."
        if intent == "route_alternatives" and tool_result:
            return f"I found alternative travel options: {tool_result}"
        if intent == "human_handoff" and tool_result:
            return "I created a human assistance request."
        if intent == "image_understanding":
            return "Image understanding is prepared in the MVP. In production this connects to Vision API or Gemini Vision."
        if intent == "voice_processing":
            return "Voice processing is prepared in the MVP. In production this connects to Speech-to-Text."
        return "Hello, I am DeBian. How can I help you?"
