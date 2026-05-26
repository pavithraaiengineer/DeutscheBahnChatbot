"""
RAG retriever.

Uses Pinecone if configured, otherwise local vector-store fallback.
Role-based access control is enforced via the `access_role` metadata field:

    access_role = "customer"  → visible to all roles
    access_role = "employee"  → visible to employee and admin only
    access_role = "admin"     → visible to admin only

Role hierarchy: customer (1) < employee (2) < admin (3)
"""

from __future__ import annotations

from app.rag.query_optimizer import optimize_query
from app.vector_db.pinecone_store import VectorStore, seed_default_documents


SEEDED = False

# ---------------------------------------------------------------------------
# Role hierarchy
# ---------------------------------------------------------------------------

_ROLE_LEVEL: dict[str, int] = {
    "customer": 1,
    "employee": 2,
    "admin":    3,
}

_DEFAULT_ROLE = "customer"


def _role_level(role: str) -> int:
    return _ROLE_LEVEL.get(role, 1)


def _filter_by_role(matches: list[dict], user_role: str) -> list[dict]:
    """
    Keep only documents the user's role is permitted to see.

    A document is accessible when:
      role_level(user_role) >= role_level(doc.access_role)

    Documents with no access_role field default to "customer" (public).
    """
    user_level = _role_level(user_role)
    allowed = []
    for m in matches:
        meta = m.get("metadata", {})
        # access_role stored in metadata by Pinecone, or directly on the doc
        doc_access = meta.get("access_role") or m.get("access_role", "customer")
        if user_level >= _role_level(doc_access):
            allowed.append(m)
    return allowed


def retrieve_context(
    query: str,
    language: str = "auto",
    top_k: int = 5,
    document_type: str | None = None,
    user_role: str = _DEFAULT_ROLE,
) -> dict:
    global SEEDED

    optimized = optimize_query(query, language=language, document_type=document_type)

    if not SEEDED:
        seed_default_documents()
        SEEDED = True

    # Fetch more candidates so filtering doesn't starve results
    result = VectorStore().query(
        optimized["optimized_query"],
        top_k=top_k * 3,
        metadata_filter=optimized["metadata_filter"],
    )

    # Enforce role-based access control
    filtered_matches = _filter_by_role(result["matches"], user_role)

    return {
        "query":              query,
        "optimized_query":    optimized,
        "vector_store_mode":  result["mode"],
        "documents":          filtered_matches[:top_k],
        "user_role":          user_role,
    }


def upsert_rag_documents(documents: list[dict]) -> dict:
    return VectorStore().upsert_documents(documents)


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
