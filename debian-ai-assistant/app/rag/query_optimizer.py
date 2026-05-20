"""
Query optimization module.

Production replacement:
- LangChain query rewriting chain
- multilingual query expansion
- metadata filtering
- Pinecone hybrid search
"""


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


def optimize_query(query: str, language: str = "auto") -> dict:
    detected_language = detect_language(query) if language == "auto" else language

    synonyms = {
        "en": {
            "delay": ["late train", "delayed train", "arrival delay", "departure delay"],
            "compensation": ["refund", "claim", "passenger rights", "voucher"],
        },
        "de": {
            "verspätung": ["Zugverspätung", "späte Ankunft", "späte Abfahrt"],
            "entschädigung": ["Erstattung", "Fahrgastrechte", "Gutschein"],
        },
    }

    expansions = []
    for key, values in synonyms.get(detected_language, {}).items():
        if key.lower() in query.lower():
            expansions.extend(values)

    optimized_query = query
    if expansions:
        optimized_query = f"{query} {' '.join(expansions)}"

    return {
        "original_query": query,
        "optimized_query": optimized_query,
        "language": detected_language,
        "expansions": expansions,
    }
