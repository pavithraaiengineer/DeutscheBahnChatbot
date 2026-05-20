"""
RAG retriever.

MVP uses an in-memory knowledge base.
Production replacement:
- Pinecone vector DB
- embeddings
- metadata filters: language, document_type, source, validity dates
- Databricks Vector Search can be used as an alternative
"""

from __future__ import annotations

from app.rag.query_optimizer import optimize_query


KNOWLEDGE_BASE = [
    {
        "id": "passenger_rights_delay_en",
        "language": "en",
        "document_type": "passenger_rights",
        "text": "For train delays, compensation may be available depending on delay duration and ticket conditions.",
    },
    {
        "id": "passenger_rights_delay_de",
        "language": "de",
        "document_type": "passenger_rights",
        "text": "Bei Zugverspätungen kann abhängig von der Dauer der Verspätung und den Ticketbedingungen eine Entschädigung möglich sein.",
    },
    {
        "id": "refund_methods_en",
        "language": "en",
        "document_type": "refund",
        "text": "Refunds can be processed to a bank account or as a voucher. Account numbers must be masked in the UI.",
    },
    {
        "id": "human_support_en",
        "language": "en",
        "document_type": "support",
        "text": "Customers can request human assistance when automated support is insufficient.",
    },
]


def retrieve_context(query: str, language: str = "auto", top_k: int = 3) -> dict:
    optimized = optimize_query(query, language)
    query_text = optimized["optimized_query"].lower()
    lang = optimized["language"]

    scored = []
    for doc in KNOWLEDGE_BASE:
        score = 0
        if doc["language"] == lang:
            score += 2
        for token in query_text.split():
            if token.strip(".,!?").lower() in doc["text"].lower():
                score += 1
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda item: item[0], reverse=True)

    return {
        "query": query,
        "optimized_query": optimized,
        "documents": [doc for _, doc in scored[:top_k]],
    }
