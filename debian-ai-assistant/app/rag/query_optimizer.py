"""
Query optimization.

Includes:
- language detection (en, de, fr, es, it, tr, pl, ar, ta)
- query expansion
- metadata filter suggestions for vector search
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_LANG_MARKERS: dict[str, list[str]] = {
    "de": [
        "zug", "verspätung", "erstattung", "entschädigung", "gutschein",
        "bahnhof", "hilfe", "fahrkarte", "gleis", "abfahrt", "ankunft",
        "verbindung", "ersatz", "ich", "bitte", "danke", "hallo",
    ],
    "fr": [
        "train", "retard", "remboursement", "indemnisation", "bon",
        "gare", "aide", "billet", "quai", "départ", "arrivée",
        "connexion", "bonjour", "merci", "s'il vous plaît",
    ],
    "es": [
        "tren", "retraso", "reembolso", "compensación", "bono",
        "estación", "ayuda", "billete", "andén", "salida", "llegada",
        "hola", "gracias", "por favor",
    ],
    "it": [
        "treno", "ritardo", "rimborso", "indennizzo", "voucher",
        "stazione", "aiuto", "biglietto", "binario", "partenza",
        "arrivo", "ciao", "grazie", "prego",
    ],
    "tr": [
        "tren", "gecikme", "geri ödeme", "tazminat", "kupon",
        "istasyon", "yardım", "bilet", "peron", "kalkış", "varış",
        "merhaba", "teşekkür",
    ],
    "pl": [
        "pociąg", "opóźnienie", "zwrot", "odszkodowanie", "kupon",
        "stacja", "pomoc", "bilet", "peron", "odjazd", "przyjazd",
        "cześć", "dziękuję", "proszę",
    ],
    "ar": [
        "قطار", "تأخير", "استرداد", "تعويض", "قسيمة",
        "محطة", "مساعدة", "تذكرة", "رصيف", "مغادرة",
    ],
    "ta": [
        "ரயில்", "தாமதம்", "உதவி", "பணம்", "நிலையம்",
        "டிக்கெட்", "தளம்",
    ],
}


def detect_language(text: str | None) -> str:
    """Return ISO 639-1 language code for *text*, defaulting to ``'en'``."""
    if not text:
        return "en"

    lowered = text.lower()

    # Score each candidate language by counting marker hits.
    scores: dict[str, int] = {}
    for lang, markers in _LANG_MARKERS.items():
        score = sum(1 for m in markers if m in lowered)
        if score:
            scores[lang] = score

    if not scores:
        return "en"

    # Return the language with the highest hit count.
    return max(scores, key=lambda k: scores[k])


# ---------------------------------------------------------------------------
# Metadata filter
# ---------------------------------------------------------------------------

def build_metadata_filter(language: str, document_type: str | None = None) -> dict:
    metadata_filter = {
        "language": language,
        "region": "germany",
    }
    if document_type:
        metadata_filter["document_type"] = document_type
    return metadata_filter


# ---------------------------------------------------------------------------
# Query optimisation
# ---------------------------------------------------------------------------

_SYNONYMS: dict[str, dict[str, list[str]]] = {
    "en": {
        "delay":          ["late train", "delayed train", "arrival delay", "departure delay"],
        "compensation":   ["refund", "claim", "passenger rights", "voucher"],
        "ticket":         ["booking", "fare", "seat reservation"],
        # employee topics
        "occupancy":      ["train full", "capacity", "seats available", "occupancy threshold",
                           "occupancy status", "how full", "FULL AMBER RED GREEN"],
        "escalation":     ["escalation matrix", "escalate", "tier", "team leader", "supervisor",
                           "station manager", "who to contact", "handoff"],
        "crew":           ["announcement", "script", "staff communication", "prohibited phrases",
                           "train crew", "passenger communication"],
        "fraud":          ["fraud detection", "duplicate claim", "fake receipt", "inflated price",
                           "suspicious claim", "false delay"],
        "pre-approval":   ["on-site compensation", "counter approval", "immediate compensation",
                           "Soforterstattung", "pre approve"],
        # admin topics
        "budget":         ["compensation budget", "quarterly budget", "annual budget",
                           "financial allocation", "spending limit", "budget cap"],
        "kpi":            ["KPI targets", "performance targets", "NPS", "CSAT", "resolution rate",
                           "automated resolution", "latency target", "handoff rate"],
        "analytics":      ["delay root cause", "worst routes", "delay statistics", "performance report",
                           "route analysis", "incident breakdown"],
        "pricing":        ["pricing strategy", "voucher preference", "cost recovery",
                           "statutory minimisation", "extraordinary circumstances exclusion"],
        "vendor":         ["vendor contract", "OpenAI contract", "Pinecone contract", "GCP contract",
                           "API contract", "DPA", "data processing agreement"],
        "config":         ["system configuration", "system config", "rate limit", "audit trail",
                           "maintenance window", "LLM configuration", "vector store config"],
    },
    "de": {
        "verspätung":     ["Zugverspätung", "späte Ankunft", "späte Abfahrt"],
        "entschädigung":  ["Erstattung", "Fahrgastrechte", "Gutschein"],
        "ticket":         ["Fahrkarte", "Buchung", "Reservierung"],
        # Mitarbeiter-Themen
        "auslastung":     ["Zugauslastung", "Kapazität", "Sitzplätze", "Auslastungsschwellen",
                           "wie voll", "VOLL ORANGE ROT GRÜN"],
        "eskalation":     ["Eskalationsmatrix", "eskalieren", "Teamleiter", "Stationsleiter",
                           "Vorgesetzter", "wen kontaktieren"],
        "betrug":         ["Betrugserkennung", "Doppelantrag", "gefälschter Beleg",
                           "überhöhter Preis", "verdächtiger Antrag"],
        "vorabgenehmigung": ["Soforterstattung", "Schalter-Genehmigung", "Vor-Ort-Genehmigung"],
        # Admin-Themen
        "budget":         ["Entschädigungsbudget", "Quartalsbudget", "Jahresbudget",
                           "Finanzierungslimit", "Budgetobergrenze"],
        "kpi":            ["KPI-Ziele", "Leistungsziele", "Lösungsrate", "Weiterleitungsrate"],
        "analytik":       ["Ursachenanalyse", "schlechteste Strecken", "Verspätungsstatistik"],
    },
    "fr": {
        "retard":        ["train en retard", "retard d'arrivée", "retard de départ"],
        "remboursement": ["indemnisation", "droits passagers", "bon"],
        "billet":        ["réservation", "tarif"],
    },
    "es": {
        "retraso":       ["tren retrasado", "retraso llegada", "retraso salida"],
        "compensación":  ["reembolso", "derechos pasajero", "bono"],
        "billete":       ["reserva", "tarifa"],
    },
    "it": {
        "ritardo":       ["treno in ritardo", "ritardo arrivo", "ritardo partenza"],
        "indennizzo":    ["rimborso", "diritti passeggeri", "voucher"],
        "biglietto":     ["prenotazione", "tariffa"],
    },
    "tr": {
        "gecikme":       ["geç kalan tren", "varış gecikmesi", "kalkış gecikmesi"],
        "tazminat":      ["geri ödeme", "yolcu hakları", "kupon"],
        "bilet":         ["rezervasyon", "ücret"],
    },
    "pl": {
        "opóźnienie":    ["spóźniony pociąg", "opóźnienie przyjazdu", "opóźnienie odjazdu"],
        "odszkodowanie": ["zwrot", "prawa pasażera", "kupon"],
        "bilet":         ["rezerwacja", "opłata"],
    },
}


def optimize_query(query: str, language: str = "auto", document_type: str | None = None) -> dict:
    detected_language = detect_language(query) if language == "auto" else language

    expansions: list[str] = []
    for key, values in _SYNONYMS.get(detected_language, {}).items():
        if key.lower() in query.lower():
            expansions.extend(values)

    optimized_query = f"{query} {' '.join(expansions)}".strip()

    return {
        "original_query":    query,
        "optimized_query":   optimized_query,
        "language":          detected_language,
        "metadata_filter":   build_metadata_filter(detected_language, document_type),
        "expansions":        expansions,
    }
