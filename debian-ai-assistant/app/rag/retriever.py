"""
RAG retriever — hard fix version.

This file intentionally avoids LangChain's PineconeVectorStore because the
LangChain retriever was still creating 1536-dimensional OpenAI embeddings while
the project's Pinecone index is 128-dimensional.

It uses app.vector_db.pinecone_store.VectorStore, which already queries Pinecone
with the project's 128-dimensional hashing_embedding().
"""

from __future__ import annotations

from app.rag.query_optimizer import optimize_query
from app.vector_db.pinecone_store import VectorStore

_ROLE_LEVEL: dict[str, int] = {"customer": 1, "employee": 2, "admin": 3}
_DEFAULT_ROLE = "customer"


def _role_level(role: str) -> int:
    return _ROLE_LEVEL.get((role or _DEFAULT_ROLE).lower(), 1)


def _allowed_for_role(metadata: dict, user_role: str) -> bool:
    required_role = metadata.get("access_role", "customer")
    return _role_level(user_role) >= _role_level(required_role)


_STORE: VectorStore | None = None


def _get_store() -> VectorStore:
    global _STORE
    if _STORE is None:
        _STORE = VectorStore()
    return _STORE


def reset_store_cache() -> None:
    """Reset cached vector store. Useful in tests/evaluations after env changes."""
    global _STORE
    _STORE = None


def retrieve_context(
    query: str,
    language: str = "auto",
    top_k: int = 5,
    document_type: str | None = None,
    user_role: str = _DEFAULT_ROLE,
) -> dict:
    optimized = optimize_query(query, language=language, document_type=document_type)

    metadata_filter: dict[str, str] = {}
    if language and language != "auto":
        metadata_filter["language"] = language
    if document_type:
        metadata_filter["document_type"] = document_type

    store = _get_store()

    # Fetch extra candidates so role filtering does not starve final results.
    result = store.query(
        optimized["optimized_query"],
        top_k=max(top_k * 3, top_k),
        metadata_filter=metadata_filter,
    )

    documents: list[dict] = []
    for match in result.get("matches", []):
        metadata = match.get("metadata") or {}
        if not _allowed_for_role(metadata, user_role):
            continue

        documents.append(
            {
                "id": match.get("id") or metadata.get("id", ""),
                "score": match.get("score", metadata.get("confidence_score", 0.0)),
                "metadata": metadata,
                "text": metadata.get("text", ""),
            }
        )

        if len(documents) >= top_k:
            break

    return {
        "query": query,
        "optimized_query": optimized,
        "vector_store_mode": result.get("mode", getattr(store, "mode", "unknown")),
        "documents": documents,
        "user_role": user_role,
    }


def search_rag(
    query: str,
    language: str = "auto",
    top_k: int = 3,
    document_type: str | None = None,
    user_role: str = _DEFAULT_ROLE,
) -> dict:
    return retrieve_context(
        query,
        language=language,
        top_k=top_k,
        document_type=document_type,
        user_role=user_role,
    )


def upsert_rag_documents(documents: list[dict]) -> dict:
    store = _get_store()
    return store.upsert_documents(documents)