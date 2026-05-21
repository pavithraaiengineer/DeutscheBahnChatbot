"""
RAG retriever.

Uses Pinecone if configured, otherwise local vector-store fallback.
"""

from __future__ import annotations

from app.rag.query_optimizer import optimize_query
from app.vector_db.pinecone_store import VectorStore, seed_default_documents


SEEDED = False


def retrieve_context(query: str, language: str = "auto", top_k: int = 3, document_type: str | None = None) -> dict:
    global SEEDED

    optimized = optimize_query(query, language=language, document_type=document_type)

    if not SEEDED:
        seed_default_documents()
        SEEDED = True

    result = VectorStore().query(
        optimized["optimized_query"],
        top_k=top_k,
        metadata_filter=optimized["metadata_filter"],
    )

    return {
        "query": query,
        "optimized_query": optimized,
        "vector_store_mode": result["mode"],
        "documents": result["matches"],
    }


def upsert_rag_documents(documents: list[dict]) -> dict:
    return VectorStore().upsert_documents(documents)


def search_rag(query: str, language: str = "auto", top_k: int = 3, document_type: str | None = None) -> dict:
    return retrieve_context(query, language=language, top_k=top_k, document_type=document_type)
