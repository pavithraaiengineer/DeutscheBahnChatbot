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


# ---------------------------------------------------------------------------
# Intent keyword sets — one entry per supported language
# Keys are lower-cased fragments; values are the intent they map to.
# ---------------------------------------------------------------------------

_DELAY_WORDS = [
    # en
    "delay", "delayed", "late",
    # de
    "verspätung", "zug verspätet", "verspätet",
    # fr
    "retard", "retardé", "en retard",
    # es
    "retraso", "retrasado",
    # it
    "ritardo", "in ritardo",
    # tr
    "gecikme", "gecikmeli",
    # pl
    "opóźnienie", "spóźniony",
    # ar
    "تأخير",
    # ta
    "தாமதம்",
]

_COMPENSATION_WORDS = [
    # en
    "refund", "compensation", "claim", "voucher", "reimburse",
    # de
    "erstattung", "entschädigung", "gutschein",
    # fr
    "remboursement", "indemnisation", "bon",
    # es
    "reembolso", "compensación", "bono",
    # it
    "rimborso", "indennizzo", "voucher",
    # tr
    "geri ödeme", "tazminat", "kupon",
    # pl
    "zwrot", "odszkodowanie", "kupon",
    # ar
    "استرداد", "تعويض",
    # ta
    "பணம்",
]

_ROUTE_WORDS = [
    # en
    "route", "alternative", "connection",
    # de
    "verbindung", "ersatz", "alternativ",
    # fr
    "itinéraire", "alternatif", "correspondance",
    # es
    "ruta", "alternativa", "conexión",
    # it
    "percorso", "alternativa", "coincidenza",
    # tr
    "güzergah", "alternatif", "bağlantı",
    # pl
    "trasa", "alternatywa", "połączenie",
    # ar
    "مسار", "بديل",
    # ta
    "வழி",
]

_HUMAN_WORDS = [
    # en
    "human", "agent", "call", "help", "callback", "staff",
    # de
    "mitarbeiter", "anrufen", "mensch", "berater",
    # fr
    "humain", "agent", "appel", "aide", "conseiller",
    # es
    "humano", "agente", "llamada", "ayuda", "asesor",
    # it
    "umano", "agente", "chiamata", "aiuto", "consulente",
    # tr
    "insan", "ajan", "arama", "yardım",
    # pl
    "człowiek", "agent", "połączenie", "pomoc",
    # ar
    "مساعدة بشرية", "وكيل",
    # ta
    "உதவி",
]

# ---------------------------------------------------------------------------
# Per-language UI strings for fallback responses (no LLM available)
# ---------------------------------------------------------------------------

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "greeting":           "Hello! I am DeBian, your Digital Rail Assistant. I can help with train delays, compensation claims, alternative routes, and human support.",
        "comp_guidance":      "I can guide you through a compensation claim step by step. Please choose Claim compensation and provide train number, station, planned time, actual time or not started, delay minutes, alternative transport, ticket price, and refund method.",
        "image":              "Image understanding is prepared. In production this connects to Gemini Vision or Vision API.",
        "voice":              "Voice processing is prepared. In production this connects to Speech-to-Text.",
        "handoff":            "I created a human assistance request. Reference: {id}. A support agent will continue from this case.",
        "alt_not_found":      "I could not find alternative routes yet.",
        "alt_found":          "I found these alternative travel options:",
        "alt_item":           "{n}. {desc} — Confidence: {score}",
    },
    "de": {
        "greeting":           "Hallo! Ich bin DeBian, Ihr digitaler Bahnassistent. Ich helfe bei Verspätungen, Entschädigungen, Alternativrouten und menschlicher Unterstützung.",
        "comp_guidance":      "Ich kann Sie Schritt für Schritt durch die Entschädigungsanfrage führen. Bitte geben Sie Zugnummer, Bahnhof, geplante Zeit, tatsächliche Zeit, Verspätung, alternative Reiseoption, Ticketpreis und Erstattungsmethode an.",
        "image":              "Bildverständnis ist vorbereitet. In der Produktion wird dies mit Gemini Vision oder Vision API verbunden.",
        "voice":              "Sprachverarbeitung ist vorbereitet. In der Produktion wird dies mit Speech-to-Text verbunden.",
        "handoff":            "Ich habe eine Anfrage für menschliche Unterstützung erstellt. Referenz: {id}.",
        "alt_not_found":      "Ich konnte noch keine Alternativrouten finden.",
        "alt_found":          "Ich habe diese alternativen Reisemöglichkeiten gefunden:",
        "alt_item":           "{n}. {desc} — Konfidenz: {score}",
    },
    "fr": {
        "greeting":           "Bonjour ! Je suis DeBian, votre assistant ferroviaire numérique. Je peux vous aider avec les retards, les indemnisations, les itinéraires alternatifs et le support humain.",
        "comp_guidance":      "Je peux vous guider étape par étape dans votre demande d'indemnisation. Veuillez fournir le numéro de train, la gare, l'heure prévue, l'heure réelle, le retard, le transport alternatif, le prix du billet et le mode de remboursement.",
        "image":              "La compréhension d'image est préparée. En production, cela se connecte à Gemini Vision ou Vision API.",
        "voice":              "Le traitement vocal est préparé. En production, cela se connecte à Speech-to-Text.",
        "handoff":            "J'ai créé une demande d'assistance humaine. Référence : {id}. Un agent de support prendra en charge votre dossier.",
        "alt_not_found":      "Je n'ai pas encore trouvé d'itinéraires alternatifs.",
        "alt_found":          "J'ai trouvé ces options de voyage alternatives :",
        "alt_item":           "{n}. {desc} — Confiance : {score}",
    },
    "es": {
        "greeting":           "¡Hola! Soy DeBian, su asistente ferroviario digital. Puedo ayudarle con retrasos, reclamaciones, rutas alternativas y soporte humano.",
        "comp_guidance":      "Puedo guiarle paso a paso en su reclamación de compensación. Proporcione número de tren, estación, hora prevista, hora real, minutos de retraso, transporte alternativo, precio del billete y método de reembolso.",
        "image":              "La comprensión de imágenes está preparada. En producción se conecta a Gemini Vision o Vision API.",
        "voice":              "El procesamiento de voz está preparado. En producción se conecta a Speech-to-Text.",
        "handoff":            "He creado una solicitud de asistencia humana. Referencia: {id}. Un agente de soporte continuará con su caso.",
        "alt_not_found":      "Aún no pude encontrar rutas alternativas.",
        "alt_found":          "Encontré estas opciones de viaje alternativas:",
        "alt_item":           "{n}. {desc} — Confianza: {score}",
    },
    "it": {
        "greeting":           "Salve! Sono DeBian, il suo assistente ferroviario digitale. Posso aiutarla con ritardi, richieste di indennizzo, percorsi alternativi e supporto umano.",
        "comp_guidance":      "Posso guidarla passo dopo passo nella richiesta di indennizzo. Fornisca numero treno, stazione, orario previsto, orario effettivo, ritardo, trasporto alternativo, prezzo del biglietto e metodo di rimborso.",
        "image":              "La comprensione delle immagini è pronta. In produzione si collega a Gemini Vision o Vision API.",
        "voice":              "L'elaborazione vocale è pronta. In produzione si collega a Speech-to-Text.",
        "handoff":            "Ho creato una richiesta di assistenza umana. Riferimento: {id}. Un agente di supporto continuerà con il suo caso.",
        "alt_not_found":      "Non ho ancora trovato percorsi alternativi.",
        "alt_found":          "Ho trovato queste opzioni di viaggio alternative:",
        "alt_item":           "{n}. {desc} — Affidabilità: {score}",
    },
    "tr": {
        "greeting":           "Merhaba! Ben DeBian, dijital demiryolu asistanınızım. Gecikmeler, tazminat talepleri, alternatif güzergahlar ve insani destek konularında yardımcı olabilirim.",
        "comp_guidance":      "Tazminat talebinizde size adım adım rehberlik edebilirim. Lütfen tren numarası, istasyon, planlanan saat, gerçek saat, gecikme dakikaları, alternatif ulaşım, bilet fiyatı ve iade yöntemini sağlayın.",
        "image":              "Görüntü anlama hazır. Üretimde Gemini Vision veya Vision API'ye bağlanır.",
        "voice":              "Ses işleme hazır. Üretimde Speech-to-Text'e bağlanır.",
        "handoff":            "Bir insani yardım talebi oluşturdum. Referans: {id}. Bir destek temsilcisi vakanızı devralacak.",
        "alt_not_found":      "Henüz alternatif güzergah bulamadım.",
        "alt_found":          "Bu alternatif seyahat seçeneklerini buldum:",
        "alt_item":           "{n}. {desc} — Güven: {score}",
    },
    "pl": {
        "greeting":           "Cześć! Jestem DeBian, Twoim cyfrowym asystentem kolejowym. Mogę pomóc z opóźnieniami, odszkodowaniami, alternatywnymi trasami i wsparciem ludzkim.",
        "comp_guidance":      "Mogę przeprowadzić Cię krok po kroku przez wniosek o odszkodowanie. Podaj numer pociągu, stację, planowy czas, rzeczywisty czas, minuty opóźnienia, alternatywny transport, cenę biletu i metodę zwrotu.",
        "image":              "Rozumienie obrazów jest gotowe. W produkcji łączy się z Gemini Vision lub Vision API.",
        "voice":              "Przetwarzanie głosu jest gotowe. W produkcji łączy się z Speech-to-Text.",
        "handoff":            "Stworzyłem wniosek o pomoc ludzką. Referencja: {id}. Agent wsparcia przejmie Twoją sprawę.",
        "alt_not_found":      "Nie znalazłem jeszcze alternatywnych tras.",
        "alt_found":          "Znalazłem te alternatywne opcje podróży:",
        "alt_item":           "{n}. {desc} — Pewność: {score}",
    },
    "ar": {
        "greeting":           "مرحباً! أنا DeBian، مساعدك الرقمي للسكك الحديدية. يمكنني مساعدتك في حالات التأخير والتعويضات والمسارات البديلة والدعم البشري.",
        "comp_guidance":      "يمكنني إرشادك خطوة بخطوة في طلب التعويض. يرجى تقديم رقم القطار، المحطة، الوقت المخطط، الوقت الفعلي، دقائق التأخير، وسيلة النقل البديلة، سعر التذكرة وطريقة الاسترداد.",
        "image":              "فهم الصور جاهز. في الإنتاج يتصل بـ Gemini Vision أو Vision API.",
        "voice":              "معالجة الصوت جاهزة. في الإنتاج تتصل بـ Speech-to-Text.",
        "handoff":            "أنشأت طلب مساعدة بشرية. المرجع: {id}. سيتولى وكيل الدعم قضيتك.",
        "alt_not_found":      "لم أتمكن من العثور على مسارات بديلة بعد.",
        "alt_found":          "وجدت خيارات السفر البديلة التالية:",
        "alt_item":           "{n}. {desc} — الثقة: {score}",
    },
    "ta": {
        "greeting":           "வணக்கம்! நான் DeBian, உங்கள் டிஜிட்டல் ரயில் உதவியாளர். தாமதங்கள், இழப்பீடு கோரிக்கைகள், மாற்று பாதைகள் மற்றும் மனித ஆதரவில் உதவ முடியும்.",
        "comp_guidance":      "இழப்பீடு கோரிக்கையில் படிப்படியாக உங்களுக்கு வழிகாட்ட முடியும். ரயில் எண், நிலையம், திட்டமிட்ட நேரம், உண்மையான நேரம், தாமத நிமிடங்கள், மாற்று போக்குவரத்து, டிக்கெட் விலை மற்றும் திரும்ப செலுத்தும் முறை வழங்கவும்.",
        "image":              "படம் புரிந்துகொள்ளுதல் தயாராக உள்ளது. உற்பத்தியில் Gemini Vision அல்லது Vision API உடன் இணைகிறது.",
        "voice":              "குரல் செயலாக்கம் தயாராக உள்ளது. உற்பத்தியில் Speech-to-Text உடன் இணைகிறது.",
        "handoff":            "மனித உதவி கோரிக்கையை உருவாக்கினேன். குறிப்பு: {id}. ஒரு ஆதரவு முகவர் உங்கள் வழக்கை தொடர்வார்.",
        "alt_not_found":      "மாற்று பாதைகளை இன்னும் கண்டுபிடிக்க முடியவில்லை.",
        "alt_found":          "இந்த மாற்று பயண விருப்பங்களை கண்டேன்:",
        "alt_item":           "{n}. {desc} — நம்பகத்தன்மை: {score}",
    },
}


def _s(language: str, key: str) -> str:
    """Return a UI string for *language*, falling back to English."""
    return _STRINGS.get(language, _STRINGS["en"]).get(key, _STRINGS["en"][key])


# ---------------------------------------------------------------------------
# MCP tool registry (unchanged)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

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
        if any(w in text for w in _DELAY_WORDS):
            return "delay_lookup"
        if any(w in text for w in _COMPENSATION_WORDS):
            return "compensation_guidance"
        if any(w in text for w in _ROUTE_WORDS):
            return "route_alternatives"
        if any(w in text for w in _HUMAN_WORDS):
            return "human_handoff"
        if payload.get("image_uploaded"):
            return "image_understanding"
        if payload.get("voice_uploaded"):
            return "voice_processing"
        return "general"

    def respond(self, message: str, payload: dict | None = None, history: list | None = None, user_role: str = "customer") -> dict:
        payload = payload or {}
        language = payload.get("language") or detect_language(message)
        intent = self.classify_intent(message, payload)

        rag_context = retrieve_context(mask_pii_text(message), language=language, user_role=user_role)

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
            history=history or [],
        )

        response = {
            "assistant":     "DeBian",
            "language":      language,
            "intent":        intent,
            "selected_tool": selected_tool,
            "response":      mask_pii_text(llm_result["text"]),
            "used_llm":      llm_result["used_llm"],
            "llm_status":    llm_result["llm_status"],
            "tool_result":   sanitize_payload(tool_result or {}),
            "rag_context":   rag_context,
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
                "message":       mask_pii_text(message),
                "language":      language,
                "intent":        intent,
                "selected_tool": selected_tool,
                "used_llm":      llm_result["used_llm"],
                "tool_result":   tool_result or {},
            },
        )

        write_audit_event("debian-agent", "respond", intent, {"selected_tool": selected_tool})
        response["evaluation"] = evaluate_response(message, response)
        return response

    # ------------------------------------------------------------------
    # Fallback response builder — multilingual
    # ------------------------------------------------------------------

    def _build_fallback_response(self, intent: str, language: str, tool_result: dict | None) -> str:
        if intent == "delay_lookup" and tool_result:
            return format_delay_response(tool_result, language=language)
        if intent == "compensation_claim" and tool_result:
            return format_compensation_response(tool_result, language=language)
        if intent == "compensation_guidance":
            return _s(language, "comp_guidance")
        if intent == "route_alternatives" and tool_result:
            return format_route_response(tool_result, language=language)
        if intent == "human_handoff" and tool_result:
            handoff_id = tool_result.get("handoff_id", "created")
            return _s(language, "handoff").format(id=handoff_id)
        if intent == "image_understanding":
            return _s(language, "image")
        if intent == "voice_processing":
            return _s(language, "voice")
        return _s(language, "greeting")


# ---------------------------------------------------------------------------
# Response formatters
# ---------------------------------------------------------------------------

# Per-language labels used inside format_delay_response
_DELAY_LABELS: dict[str, dict[str, str]] = {
    "en": {"status": "Status for {train}", "delay": "The current delay is approximately {n} minutes.",
           "route": "Route: {o} → {d}.", "station": "Station: {s}.", "planned": "Planned start time: {t}.",
           "actual": "Actual start time: {t}.", "platform": "Platform: {p}.",
           "demo": "Note: this is demo data. For live data, configure DB API credentials.",
           "unknown": "I could not find delay data for {train} yet. For the demo, try ICE 572, ICE 999, or RE 50.",
           "eligible": "You may be able to continue with a compensation claim."},
    "de": {"status": "Status für {train}", "delay": "Die aktuelle Verspätung beträgt ungefähr {n} Minuten.",
           "route": "Route: {o} → {d}.", "station": "Bahnhof: {s}.", "planned": "Geplante Startzeit: {t}.",
           "actual": "Tatsächliche Startzeit: {t}.", "platform": "Gleis: {p}.",
           "demo": "Hinweis: Diese Antwort nutzt Demo-Daten. Für Live-Daten bitte DB API-Zugangsdaten konfigurieren.",
           "unknown": "Für {train} habe ich noch keine Verspätungsdaten. Für die Demo: ICE 572, ICE 999 oder RE 50.",
           "eligible": "Möglicherweise haben Sie Anspruch auf eine Entschädigung."},
    "fr": {"status": "Statut pour {train}", "delay": "Le retard actuel est d'environ {n} minutes.",
           "route": "Itinéraire : {o} → {d}.", "station": "Gare : {s}.", "planned": "Heure de départ prévue : {t}.",
           "actual": "Heure de départ réelle : {t}.", "platform": "Voie : {p}.",
           "demo": "Remarque : ceci est une démo. Pour les données en direct, configurez les identifiants de l'API DB.",
           "unknown": "Je n'ai pas trouvé de données pour {train}. Essayez ICE 572, ICE 999 ou RE 50.",
           "eligible": "Vous pourriez être éligible à une indemnisation."},
    "es": {"status": "Estado para {train}", "delay": "El retraso actual es de aproximadamente {n} minutos.",
           "route": "Ruta: {o} → {d}.", "station": "Estación: {s}.", "planned": "Hora de salida prevista: {t}.",
           "actual": "Hora de salida real: {t}.", "platform": "Andén: {p}.",
           "demo": "Nota: estos son datos de demostración. Configure las credenciales de la API de DB para datos en vivo.",
           "unknown": "No encontré datos para {train}. Pruebe ICE 572, ICE 999 o RE 50.",
           "eligible": "Es posible que pueda solicitar una compensación."},
    "it": {"status": "Stato per {train}", "delay": "Il ritardo attuale è di circa {n} minuti.",
           "route": "Percorso: {o} → {d}.", "station": "Stazione: {s}.", "planned": "Orario di partenza previsto: {t}.",
           "actual": "Orario di partenza effettivo: {t}.", "platform": "Binario: {p}.",
           "demo": "Nota: questi sono dati demo. Per dati live, configurare le credenziali API DB.",
           "unknown": "Non ho trovato dati per {train}. Provi ICE 572, ICE 999 o RE 50.",
           "eligible": "Potrebbe essere idoneo a una richiesta di indennizzo."},
    "tr": {"status": "{train} için durum", "delay": "Mevcut gecikme yaklaşık {n} dakikadır.",
           "route": "Güzergah: {o} → {d}.", "station": "İstasyon: {s}.", "planned": "Planlanan kalkış saati: {t}.",
           "actual": "Gerçek kalkış saati: {t}.", "platform": "Peron: {p}.",
           "demo": "Not: Bu demo verisidir. Canlı veriler için DB API kimlik bilgilerini yapılandırın.",
           "unknown": "{train} için gecikme verisi bulunamadı. ICE 572, ICE 999 veya RE 50 deneyin.",
           "eligible": "Tazminat talebinde bulunabilirsiniz."},
    "pl": {"status": "Status dla {train}", "delay": "Obecne opóźnienie wynosi około {n} minut.",
           "route": "Trasa: {o} → {d}.", "station": "Stacja: {s}.", "planned": "Planowy czas odjazdu: {t}.",
           "actual": "Rzeczywisty czas odjazdu: {t}.", "platform": "Peron: {p}.",
           "demo": "Uwaga: to są dane demonstracyjne. Dla danych na żywo skonfiguruj dane API DB.",
           "unknown": "Nie znalazłem danych dla {train}. Spróbuj ICE 572, ICE 999 lub RE 50.",
           "eligible": "Możesz ubiegać się o odszkodowanie."},
    "ar": {"status": "الحالة لـ {train}", "delay": "التأخير الحالي حوالي {n} دقيقة.",
           "route": "المسار: {o} → {d}.", "station": "المحطة: {s}.", "planned": "وقت المغادرة المخطط: {t}.",
           "actual": "وقت المغادرة الفعلي: {t}.", "platform": "الرصيف: {p}.",
           "demo": "ملاحظة: هذه بيانات تجريبية. لبيانات مباشرة، قم بتهيئة بيانات اعتماد API.",
           "unknown": "لم أجد بيانات للقطار {train}. جرّب ICE 572 أو ICE 999 أو RE 50.",
           "eligible": "قد تكون مؤهلاً لتعويض."},
    "ta": {"status": "{train} நிலை", "delay": "தற்போதைய தாமதம் சுமார் {n} நிமிடங்கள்.",
            "route": "பாதை: {o} → {d}.", "station": "நிலையம்: {s}.", "planned": "திட்டமிட்ட நேரம்: {t}.",
            "actual": "உண்மையான நேரம்: {t}.", "platform": "தளம்: {p}.",
            "demo": "குறிப்பு: இது டெமோ தரவு. நேரடி தரவிற்கு DB API சான்றுகளை அமைக்கவும்.",
            "unknown": "{train} க்கான தரவு கிடைக்கவில்லை. ICE 572, ICE 999 அல்லது RE 50 முயற்சிக்கவும்.",
            "eligible": "இழப்பீடு கோரிக்கைக்கு தகுதியுடையவராக இருக்கலாம்."},
}


def _dl(language: str, key: str) -> str:
    """Return a delay-formatter label, falling back to English."""
    return _DELAY_LABELS.get(language, _DELAY_LABELS["en"]).get(key, _DELAY_LABELS["en"][key])


def format_delay_response(delay: dict, language: str = "en") -> str:
    train   = delay.get("train_number", "your train")
    status  = delay.get("status", "unknown")
    minutes = delay.get("delay_minutes")
    origin  = delay.get("origin") or delay.get("station_name")
    dest    = delay.get("destination")
    planned = delay.get("planned_start_time")
    actual  = delay.get("actual_start_time")
    platform = delay.get("platform") or delay.get("actual_platform") or delay.get("planned_platform")
    source  = delay.get("source", "mock")
    real_time_ready = delay.get("real_time_ready")

    if status == "unknown":
        return _dl(language, "unknown").format(train=train)

    lines = [_dl(language, "status").format(train=train) + f": {status}."]
    if minutes is not None:
        lines.append(_dl(language, "delay").format(n=minutes))
    if origin and dest:
        lines.append(_dl(language, "route").format(o=origin, d=dest))
    elif origin:
        lines.append(_dl(language, "station").format(s=origin))
    if planned:
        lines.append(_dl(language, "planned").format(t=planned))
    if actual:
        lines.append(_dl(language, "actual").format(t=actual))
    if platform:
        lines.append(_dl(language, "platform").format(p=platform))
    if source.startswith("mock") or real_time_ready is False:
        lines.append(_dl(language, "demo"))
    if minutes is not None and minutes >= 60:
        lines.append(_dl(language, "eligible"))
    return "\n".join(lines)


# Per-language labels for compensation response
_COMP_LABELS: dict[str, dict[str, str]] = {
    "en": {"submitted": "Your compensation claim has been submitted. Reference: {id}.",
           "eligible":  "Estimated compensation: {pct}% = {amt} {cur}.",
           "not_elig":  "Based on the demo rules, this journey is probably not eligible for compensation.",
           "account":   "Confirmed account: {acct}.",
           "voucher":   "Voucher delivery has been confirmed.",
           "pii":       "Sensitive data has been masked."},
    "de": {"submitted": "Ihre Entschädigungsanfrage wurde eingereicht. Referenz: {id}.",
           "eligible":  "Voraussichtliche Entschädigung: {pct}% = {amt} {cur}.",
           "not_elig":  "Nach den Demo-Regeln besteht voraussichtlich kein Entschädigungsanspruch.",
           "account":   "Bestätigtes Konto: {acct}.",
           "voucher":   "Der Gutscheinversand wurde bestätigt.",
           "pii":       "Ihre sensiblen Daten wurden maskiert."},
    "fr": {"submitted": "Votre demande d'indemnisation a été soumise. Référence : {id}.",
           "eligible":  "Indemnisation estimée : {pct}% = {amt} {cur}.",
           "not_elig":  "Selon les règles démo, ce trajet n'est probablement pas éligible.",
           "account":   "Compte confirmé : {acct}.",
           "voucher":   "La livraison du bon a été confirmée.",
           "pii":       "Les données sensibles ont été masquées."},
    "es": {"submitted": "Su reclamación de compensación ha sido enviada. Referencia: {id}.",
           "eligible":  "Compensación estimada: {pct}% = {amt} {cur}.",
           "not_elig":  "Según las reglas de demostración, este viaje probablemente no es elegible.",
           "account":   "Cuenta confirmada: {acct}.",
           "voucher":   "La entrega del bono ha sido confirmada.",
           "pii":       "Los datos sensibles han sido enmascarados."},
    "it": {"submitted": "La sua richiesta di indennizzo è stata inviata. Riferimento: {id}.",
           "eligible":  "Indennizzo stimato: {pct}% = {amt} {cur}.",
           "not_elig":  "In base alle regole demo, questo viaggio probabilmente non è idoneo.",
           "account":   "Conto confermato: {acct}.",
           "voucher":   "La consegna del voucher è stata confermata.",
           "pii":       "I dati sensibili sono stati mascherati."},
    "tr": {"submitted": "Tazminat talebiniz gönderildi. Referans: {id}.",
           "eligible":  "Tahmini tazminat: %{pct} = {amt} {cur}.",
           "not_elig":  "Demo kurallarına göre bu yolculuk muhtemelen tazminata hak kazanmıyor.",
           "account":   "Onaylanan hesap: {acct}.",
           "voucher":   "Kupon teslimatı onaylandı.",
           "pii":       "Hassas veriler maskelendi."},
    "pl": {"submitted": "Twoje roszczenie o odszkodowanie zostało przesłane. Referencja: {id}.",
           "eligible":  "Szacowane odszkodowanie: {pct}% = {amt} {cur}.",
           "not_elig":  "Według zasad demo ta podróż prawdopodobnie nie kwalifikuje się do odszkodowania.",
           "account":   "Potwierdzony rachunek: {acct}.",
           "voucher":   "Dostawa kuponu została potwierdzona.",
           "pii":       "Wrażliwe dane zostały zamaskowane."},
    "ar": {"submitted": "تم تقديم مطالبة التعويض الخاصة بك. المرجع: {id}.",
           "eligible":  "التعويض المقدر: {pct}٪ = {amt} {cur}.",
           "not_elig":  "وفقاً لقواعد العرض التوضيحي، هذه الرحلة غير مؤهلة للتعويض.",
           "account":   "الحساب المؤكد: {acct}.",
           "voucher":   "تم تأكيد تسليم القسيمة.",
           "pii":       "تم إخفاء البيانات الحساسة."},
    "ta": {"submitted": "உங்கள் இழப்பீடு கோரிக்கை சமர்ப்பிக்கப்பட்டது. குறிப்பு: {id}.",
            "eligible":  "மதிப்பிடப்பட்ட இழப்பீடு: {pct}% = {amt} {cur}.",
            "not_elig":  "டெமோ விதிகளின்படி, இந்த பயணம் இழப்பீட்டிற்கு தகுதியற்றது.",
            "account":   "உறுதிப்படுத்தப்பட்ட கணக்கு: {acct}.",
            "voucher":   "கூப்பன் டெலிவரி உறுதிப்படுத்தப்பட்டது.",
            "pii":       "முக்கியமான தரவு மறைக்கப்பட்டது."},
}


def _cl(language: str, key: str) -> str:
    return _COMP_LABELS.get(language, _COMP_LABELS["en"]).get(key, _COMP_LABELS["en"][key])


def format_compensation_response(result: dict, language: str = "en") -> str:
    compensation    = result.get("compensation", {})
    claim_id        = result.get("claim_id", "created")
    amount          = compensation.get("amount", 0)
    percentage      = compensation.get("percentage", 0)
    currency        = compensation.get("currency", "EUR")
    eligible        = compensation.get("eligible", False)
    masked_account  = result.get("masked_account_number")
    refund_method   = result.get("refund_method")

    lines = [_cl(language, "submitted").format(id=claim_id)]
    if eligible:
        lines.append(_cl(language, "eligible").format(pct=percentage, amt=amount, cur=currency))
    else:
        lines.append(_cl(language, "not_elig"))
    if refund_method == "bank_account" and masked_account:
        lines.append(_cl(language, "account").format(acct=masked_account))
    if refund_method == "voucher":
        lines.append(_cl(language, "voucher"))
    lines.append(_cl(language, "pii"))
    return "\n".join(lines)


def format_route_response(result: dict, language: str = "en") -> str:
    alternatives = result.get("alternatives", [])
    if not alternatives:
        return _s(language, "alt_not_found")

    lines = [_s(language, "alt_found")]
    for idx, alt in enumerate(alternatives[:3], start=1):
        lines.append(
            _s(language, "alt_item").format(
                n=idx,
                desc=alt.get("description", ""),
                score=alt.get("confidence_score", ""),
            )
        )
    return "\n".join(lines)
