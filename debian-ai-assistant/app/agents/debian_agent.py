"""
DeBian agent with optional LLM layer.

DB Flow:
1. User asks question by voice, image, or text
2. Backend receives request
3. Language is detected
4. Voice is converted to text if needed
5. Image is analyzed if uploaded
6. Agent classifies intent
7. Agent calls correct MCP-like tool
8. Delay/compensation data is retrieved
9. PII is masked
10. Response streams back to user
11. Analytics are written for BigQuery-style reporting
12. Evaluation logs are stored for quality improvement
"""

from __future__ import annotations

from app.evaluation.eval_pipeline import evaluate_response
from app.llm.openai_client import generate_llm_response
from app.rag.retriever import retrieve_context
from app.rag.query_optimizer import detect_language
from app.security.governance import write_analytics_event, write_audit_event, sanitize_payload
from app.tools.compensation_tool import submit_compensation_claim
from app.tools.delay_tool import get_delay_status
from app.tools.human_handoff_tool import request_human_handoff
from app.tools.pii_masking_tool import mask_pii_text
from app.tools.route_tool import get_alternative_routes


class MCPToolRegistry:
    def call(self, tool_name: str, payload: dict) -> dict:
        if tool_name == "delay_lookup":
            return get_delay_status(
                train_number=payload.get("train_number", ""),
                station_name=payload.get("station_name"),
                planned_start_time=payload.get("planned_start_time"),
            )
        if tool_name == "compensation_claim":
            return submit_compensation_claim(payload)
        if tool_name == "route_alternatives":
            return get_alternative_routes(payload.get("origin", ""), payload.get("destination", ""))
        if tool_name == "human_handoff":
            return request_human_handoff(
                language=payload.get("language", "en"),
                reason=payload.get("reason", "customer requested support"),
                priority=payload.get("priority", "normal"),
            )
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
        if any(word in text for word in ["human", "agent", "call", "mitarbeiter", "anrufen", "help", "callback"]):
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

        rag_context = retrieve_context(mask_pii_text(message), language=language)

        tool_result = None
        selected_tool = None

        if intent == "delay_lookup" and payload.get("train_number"):
            selected_tool = "delay_lookup"
            tool_result = self.tools.call(selected_tool, payload)
        elif intent == "compensation_claim":
            selected_tool = "compensation_claim"
            tool_result = self.tools.call(selected_tool, payload)
        elif intent == "route_alternatives":
            selected_tool = "route_alternatives"
            tool_result = self.tools.call(selected_tool, payload)
        elif intent == "human_handoff":
            selected_tool = "human_handoff"
            tool_result = self.tools.call(
                selected_tool,
                {
                    "language": language,
                    "reason": message,
                    "priority": payload.get("priority", "normal"),
                },
            )

        fallback_response = self._build_fallback_response(intent, language, tool_result)

        llm_result = generate_llm_response(
            user_message=message,
            intent=intent,
            language=language,
            rag_context=rag_context,
            tool_result=sanitize_payload(tool_result or {}),
            fallback_response=fallback_response,
        )

        response = {
            "assistant": "DeBian",
            "language": language,
            "intent": intent,
            "selected_tool": selected_tool,
            "response": mask_pii_text(llm_result["text"]),
            "used_llm": llm_result["used_llm"],
            "llm_status": llm_result["llm_status"],
            "tool_result": sanitize_payload(tool_result or {}),
            "rag_context": rag_context,
            "flow": [
                "User input received by text, voice, or image",
                "Backend receives request",
                "Language detected",
                "Voice/image placeholder handled if uploaded",
                "Agent classifies intent",
                "Agent calls MCP-like tool",
                "Delay/compensation/RAG data retrieved",
                "PII masked",
                "Response streamed/returned to the user",
                "Analytics written for BigQuery-style reporting",
                "Evaluation logs stored for quality improvement",
            ],
        }

        if llm_result.get("reason"):
            response["llm_fallback_reason"] = llm_result["reason"]

        write_analytics_event(
            "assistant_response",
            {
                "message": mask_pii_text(message),
                "language": language,
                "intent": intent,
                "selected_tool": selected_tool,
                "used_llm": llm_result["used_llm"],
                "tool_result": tool_result or {},
            },
        )

        write_audit_event("debian-agent", "respond", intent, {"selected_tool": selected_tool})
        response["evaluation"] = evaluate_response(message, response)
        return response

    def _build_fallback_response(self, intent: str, language: str, tool_result: dict | None) -> str:
        if language == "de":
            return self._build_fallback_response_de(intent, tool_result)
        return self._build_fallback_response_en(intent, tool_result)

    def _build_fallback_response_en(self, intent: str, tool_result: dict | None) -> str:
        if intent == "delay_lookup" and tool_result:
            return format_delay_response(tool_result, language="en")
        if intent == "compensation_claim" and tool_result:
            return format_compensation_response(tool_result, language="en")
        if intent == "compensation_guidance":
            return (
                "I can guide you through a compensation claim step by step. "
                "Please choose Claim compensation and provide train number, station, planned time, actual time or not started, "
                "delay minutes, alternative transport, ticket price, and refund method."
            )
        if intent == "route_alternatives" and tool_result:
            return format_route_response(tool_result, language="en")
        if intent == "human_handoff" and tool_result:
            handoff_id = tool_result.get("handoff_id", "created")
            return f"I created a human assistance request. Reference: {handoff_id}. A support agent can continue from this case."
        if intent == "image_understanding":
            return "Image understanding is prepared. In production this connects to Gemini Vision or Vision API."
        if intent == "voice_processing":
            return "Voice processing is prepared. In production this connects to Speech-to-Text."
        return "Hello Example user, I am DeBian. I can help with train delays, compensation claims, alternative routes, tickets, and human assistance."

    def _build_fallback_response_de(self, intent: str, tool_result: dict | None) -> str:
        if intent == "delay_lookup" and tool_result:
            return format_delay_response(tool_result, language="de")
        if intent == "compensation_claim" and tool_result:
            return format_compensation_response(tool_result, language="de")
        if intent == "compensation_guidance":
            return (
                "Ich kann Sie Schritt für Schritt durch die Entschädigungsanfrage führen. "
                "Bitte wählen Sie Claim compensation und geben Sie Zugnummer, Bahnhof, geplante Zeit, tatsächliche Zeit, "
                "Verspätung, alternative Reiseoption, Ticketpreis und Erstattungsmethode an."
            )
        if intent == "route_alternatives" and tool_result:
            return format_route_response(tool_result, language="de")
        if intent == "human_handoff" and tool_result:
            handoff_id = tool_result.get("handoff_id", "erstellt")
            return f"Ich habe eine Anfrage für menschliche Unterstützung erstellt. Referenz: {handoff_id}."
        return "Hallo, ich bin DeBian. Ich kann bei Verspätungen, Entschädigungen, Alternativrouten und menschlicher Unterstützung helfen."


def format_delay_response(delay: dict, language: str = "en") -> str:
    train = delay.get("train_number", "your train")
    status = delay.get("status", "unknown")
    minutes = delay.get("delay_minutes")
    origin = delay.get("origin") or delay.get("station_name")
    destination = delay.get("destination")
    planned = delay.get("planned_start_time")
    actual = delay.get("actual_start_time")
    platform = delay.get("platform") or delay.get("actual_platform") or delay.get("planned_platform")
    source = delay.get("source", "mock")
    real_time_ready = delay.get("real_time_ready")

    if status == "unknown":
        if language == "de":
            return (
                f"Ich habe für {train} noch keine Verspätungsdaten gefunden. "
                "Für die Demo funktionieren ICE 572, ICE 999 und RE 50. "
                "Für Live-Daten benötigen wir DB API-Zugangsdaten sowie Bahnhof und geplante Startzeit."
            )
        return (
            f"I could not find delay data for {train} yet. "
            "For the demo, try ICE 572, ICE 999, or RE 50. "
            "For real-time mode, DB API credentials plus station name and planned start time are needed."
        )

    if language == "de":
        lines = [f"Status für {train}: {status}."]
        if minutes is not None:
            lines.append(f"Die aktuelle Verspätung beträgt ungefähr {minutes} Minuten.")
        if origin and destination:
            lines.append(f"Route: {origin} → {destination}.")
        elif origin:
            lines.append(f"Bahnhof: {origin}.")
        if planned:
            lines.append(f"Geplante Startzeit: {planned}.")
        if actual:
            lines.append(f"Tatsächliche Startzeit: {actual}.")
        if platform:
            lines.append(f"Gleis: {platform}.")
        if source.startswith("mock") or real_time_ready is False:
            lines.append("Hinweis: Diese Antwort nutzt Demo-Daten. Für Live-Daten bitte DB API-Zugangsdaten konfigurieren.")
        return "\n".join(lines)

    lines = [f"Status for {train}: {status}."]
    if minutes is not None:
        lines.append(f"The current delay is approximately {minutes} minutes.")
    if origin and destination:
        lines.append(f"Route: {origin} → {destination}.")
    elif origin:
        lines.append(f"Station: {origin}.")
    if planned:
        lines.append(f"Planned start time: {planned}.")
    if actual:
        lines.append(f"Actual start time: {actual}.")
    if platform:
        lines.append(f"Platform: {platform}.")
    if source.startswith("mock") or real_time_ready is False:
        lines.append("Note: this is demo data. For live data, configure DB API credentials.")
    if minutes is not None and minutes >= 60:
        lines.append("You may be able to continue with a compensation claim.")
    return "\n".join(lines)


def format_compensation_response(result: dict, language: str = "en") -> str:
    compensation = result.get("compensation", {})
    claim_id = result.get("claim_id", "created")
    amount = compensation.get("amount", 0)
    percentage = compensation.get("percentage", 0)
    currency = compensation.get("currency", "EUR")
    eligible = compensation.get("eligible", False)
    masked_account = result.get("masked_account_number")
    refund_method = result.get("refund_method")

    if language == "de":
        lines = [f"Ihre Entschädigungsanfrage wurde eingereicht. Referenz: {claim_id}."]
        if eligible:
            lines.append(f"Voraussichtliche Entschädigung: {percentage}% = {amount} {currency}.")
        else:
            lines.append("Nach den Demo-Regeln besteht voraussichtlich kein Entschädigungsanspruch.")
        if refund_method == "bank_account" and masked_account:
            lines.append(f"Bestätigtes Konto: {masked_account}.")
        if refund_method == "voucher":
            lines.append("Der Gutscheinversand wurde bestätigt.")
        lines.append("Ihre sensiblen Daten wurden maskiert.")
        return "\n".join(lines)

    lines = [f"Your compensation claim has been submitted. Reference: {claim_id}."]
    if eligible:
        lines.append(f"Estimated compensation: {percentage}% = {amount} {currency}.")
    else:
        lines.append("Based on the demo rules, this journey is probably not eligible for compensation.")
    if refund_method == "bank_account" and masked_account:
        lines.append(f"Confirmed account: {masked_account}.")
    if refund_method == "voucher":
        lines.append("Voucher delivery has been confirmed.")
    lines.append("Sensitive data has been masked.")
    return "\n".join(lines)


def format_route_response(result: dict, language: str = "en") -> str:
    alternatives = result.get("alternatives", [])
    if not alternatives:
        return "I could not find alternative routes yet."

    if language == "de":
        lines = ["Ich habe diese alternativen Reisemöglichkeiten gefunden:"]
        for idx, alt in enumerate(alternatives[:3], start=1):
            lines.append(f"{idx}. {alt.get('description')} Vertrauen: {alt.get('confidence_score')}")
        return "\n".join(lines)

    lines = ["I found these alternative travel options:"]
    for idx, alt in enumerate(alternatives[:3], start=1):
        lines.append(f"{idx}. {alt.get('description')} Confidence: {alt.get('confidence_score')}")
    return "\n".join(lines)
