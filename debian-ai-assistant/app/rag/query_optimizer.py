"""
Query optimization.

Includes:
- language detection
- query expansion
- metadata filter suggestions for vector search
"""

from __future__ import annotations


def detect_language(text: str | None) -> str:
    if not text:
        return "en"

    lowered = text.lower()

    german_markers = ["zug", "verspätung", "erstattung", "entschädigung", "gutschein", "bahnhof", "hilfe"]
    tamil_markers = ["ரயில்", "தாமதம்", "உதவி", "பணம்"]

    if any(marker in lowered for marker in german_markers):
        return "de"
    if any(marker in lowered for marker in tamil_markers):
        return "ta"
    return "en"


def build_metadata_filter(language: str, document_type: str | None = None) -> dict:
    metadata_filter = {
        "language": language,
        "region": "germany",
    }

    if document_type:
        metadata_filter["document_type"] = document_type

    return metadata_filter


def optimize_query(query: str, language: str = "auto", document_type: str | None = None) -> dict:
    detected_language = detect_language(query) if language == "auto" else language

    synonyms = {
        "en": {
            "delay": ["late train", "delayed train", "arrival delay", "departure delay"],
            "compensation": ["refund", "claim", "passenger rights", "voucher"],
            "ticket": ["booking", "fare", "seat reservation"],
        },
        "de": {
            "verspätung": ["Zugverspätung", "späte Ankunft", "späte Abfahrt"],
            "entschädigung": ["Erstattung", "Fahrgastrechte", "Gutschein"],
            "ticket": ["Fahrkarte", "Buchung", "Reservierung"],
        },
    }

    expansions = []
    for key, values in synonyms.get(detected_language, {}).items():
        if key.lower() in query.lower():
            expansions.extend(values)

    optimized_query = f"{query} {' '.join(expansions)}".strip()

    return {
        "original_query": query,
        "optimized_query": optimized_query,
        "language": detected_language,
        "metadata_filter": build_metadata_filter(detected_language, document_type),
        "expansions": expansions,
    }
