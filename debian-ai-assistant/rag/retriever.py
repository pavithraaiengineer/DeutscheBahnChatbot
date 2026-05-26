"""
RAG retriever with role-based access control.

Uses Pinecone if configured, otherwise local vector-store fallback.

Role enforcement
----------------
Every document in the vector store may carry an `access_role` metadata field:

    access_role = "customer"   → visible to customer, employee, admin
    access_role = "employee"   → visible to employee and admin only
    access_role = "admin"      → visible to admin only

If `access_role` is absent the document is treated as admin-only (safe default).

The caller passes the authenticated user's role via `user_role`. Documents that
the user is not allowed to see are stripped from the result set *after* the
vector search so that the top-k count is computed over the visible subset.
"""

from __future__ import annotations

from app.auth import ROLE_HIERARCHY
from app.rag.query_optimizer import optimize_query
from app.vector_db.pinecone_store import VectorStore, seed_default_documents


SEEDED = False

# Safe default: if a document has no access_role tag, treat it as admin-only.
_DEFAULT_ACCESS_ROLE = "admin"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _role_level(role: str) -> int:
    """Return numeric level for a role string; 0 for unknown roles."""
    return ROLE_HIERARCHY.get(role, 0)


def _is_accessible(user_role: str, doc: dict) -> bool:
    """Return True if the user's role meets or exceeds the document's required role."""
    required = doc.get("access_role") or doc.get("metadata", {}).get("access_role") or _DEFAULT_ACCESS_ROLE
    return _role_level(user_role) >= _role_level(required)


def _filter_by_role(matches: list[dict], user_role: str) -> list[dict]:
    """Strip documents the caller is not allowed to see."""
    return [m for m in matches if _is_accessible(user_role, m.get("metadata", m))]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve_context(
    query: str,
    language: str = "auto",
    top_k: int = 3,
    document_type: str | None = None,
    user_role: str = "customer",
) -> dict:
    """
    Retrieve relevant RAG documents for *query*, filtered by *user_role*.

    Args:
        query:         The user's natural-language question.
        language:      Language hint ("auto", "en", "de", …).
        top_k:         Maximum number of documents to return after role filtering.
        document_type: Optional document-type filter passed to the query optimizer.
        user_role:     The authenticated caller's role ("customer", "employee", "admin").
                       Defaults to "customer" (most restrictive) if not supplied.

    Returns:
        dict with keys: query, optimized_query, vector_store_mode, documents,
                        role_filter_applied, user_role.
    """
    global SEEDED

    optimized = optimize_query(query, language=language, document_type=document_type)

    if not SEEDED:
        seed_default_documents()
        SEEDED = True

    # Fetch a larger set from the store so role filtering doesn't leave us
    # short of top_k results.
    fetch_k = top_k * 4
    result = VectorStore().query(
        optimized["optimized_query"],
        top_k=fetch_k,
        metadata_filter=optimized["metadata_filter"],
    )

    all_matches = result["matches"]
    visible_matches = _filter_by_role(all_matches, user_role)
    trimmed = visible_matches[:top_k]

    return {
        "query": query,
        "optimized_query": optimized,
        "vector_store_mode": result["mode"],
        "documents": trimmed,
        "role_filter_applied": True,
        "user_role": user_role,
        "filtered_out": len(all_matches) - len(visible_matches),
    }


def upsert_rag_documents(documents: list[dict]) -> dict:
    """Upsert documents into the vector store (admin operation)."""
    return VectorStore().upsert_documents(documents)


def search_rag(
    query: str,
    language: str = "auto",
    top_k: int = 3,
    document_type: str | None = None,
    user_role: str = "customer",
) -> dict:
    """Convenience alias for retrieve_context."""
    return retrieve_context(
        query,
        language=language,
        top_k=top_k,
        document_type=document_type,
        user_role=user_role,
    )
