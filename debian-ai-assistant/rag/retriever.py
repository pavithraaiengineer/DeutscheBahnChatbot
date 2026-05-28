"""
RAG retriever — LangChain-compatible Pinecone/local retriever.

Important fix
-------------
This project seeds Pinecone with the custom 128-dimensional hashing vectors
from app.vector_db.pinecone_store.hashing_embedding(). Therefore the retriever
must query Pinecone with the same 128-dimensional embedding function.

Do NOT use default OpenAIEmbeddings against the existing 128-dim Pinecone index:
default OpenAI embeddings are 1536 dimensions and Pinecone will reject the query.
"""

from __future__ import annotations

from typing import List

from app.config import get_env, get_int_env
from app.rag.query_optimizer import optimize_query
from app.vector_db.pinecone_store import hashing_embedding

# ---------------------------------------------------------------------------
# Role hierarchy
# ---------------------------------------------------------------------------

_ROLE_LEVEL: dict[str, int] = {"customer": 1, "employee": 2, "admin": 3}
_DEFAULT_ROLE = "customer"


def _role_level(role: str) -> int:
    return _ROLE_LEVEL.get(role, 1)


def _filter_by_role(docs, user_role: str) -> list:
    user_level = _role_level(user_role)
    allowed = []
    for doc in docs:
        doc_access = doc.metadata.get("access_role", "customer")
        if user_level >= _role_level(doc_access):
            allowed.append(doc)
    return allowed


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

class HashingEmbeddings:
    """
    LangChain-compatible embeddings wrapper around the project's existing
    128-dimensional hashing_embedding() function.

    This keeps retrieval compatible with the vectors already written by
    scripts/seed_pinecone.py and app.vector_db.pinecone_store.VectorStore.
    """

    def __init__(self, dimension: int = 128) -> None:
        self.dimension = dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [hashing_embedding(text or "", self.dimension) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return hashing_embedding(text or "", self.dimension)


# ---------------------------------------------------------------------------
# Vector store bootstrap
# ---------------------------------------------------------------------------

def _build_vectorstore():
    """Return a LangChain VectorStore: Pinecone if configured, otherwise local."""
    pinecone_key = get_env("PINECONE_API_KEY", "")
    dimension = get_int_env("PINECONE_DIMENSION", 128)
    embeddings = HashingEmbeddings(dimension=dimension)

    if pinecone_key:
        from langchain_pinecone import PineconeVectorStore

        index_name = get_env("PINECONE_INDEX_NAME", get_env("PINECONE_INDEX", "dbchatbot"))
        return PineconeVectorStore(index_name=index_name, embedding=embeddings), f"pinecone-hashing-{dimension}d"

    # Local in-memory fallback — seed from local_vector_store.json
    from langchain_core.vectorstores import InMemoryVectorStore

    store = InMemoryVectorStore(embedding=embeddings)
    _seed_in_memory(store)
    return store, f"local-hashing-{dimension}d"


def _seed_in_memory(store) -> None:
    """Load local_vector_store.json into the in-memory store."""
    import json
    from pathlib import Path
    from langchain_core.documents import Document

    path = Path("local_vector_store.json")
    if not path.exists():
        # Also support running from subfolders.
        alt = Path(__file__).resolve().parents[2] / "local_vector_store.json"
        path = alt if alt.exists() else path

    if not path.exists():
        return

    raw = json.loads(path.read_text(encoding="utf-8"))
    docs = []

    if isinstance(raw, dict) and "documents" in raw:
        entries = raw["documents"]
    elif isinstance(raw, dict):
        # Current project format: {doc_id: {"document": {...}, "vector": [...]}}
        entries = [item.get("document", item) for item in raw.values()]
    else:
        entries = raw

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        metadata = entry.get("metadata", entry)
        text = entry.get("text") or metadata.get("text", "")
        if text:
            docs.append(Document(page_content=text, metadata=metadata))

    if docs:
        store.add_documents(docs)


_STORE = None
_STORE_MODE = "local"


def _get_store():
    global _STORE, _STORE_MODE
    if _STORE is None:
        _STORE, _STORE_MODE = _build_vectorstore()
    return _STORE, _STORE_MODE


def reset_store_cache() -> None:
    """Useful in tests/evaluations after changing env vars."""
    global _STORE, _STORE_MODE
    _STORE = None
    _STORE_MODE = "local"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve_context(
    query: str,
    language: str = "auto",
    top_k: int = 5,
    document_type: str | None = None,
    user_role: str = _DEFAULT_ROLE,
) -> dict:
    optimized = optimize_query(query, language=language, document_type=document_type)
    store, mode = _get_store()

    # Fetch extra candidates so role filtering does not starve results.
    raw_docs = store.similarity_search(optimized["optimized_query"], k=top_k * 3)
    filtered = _filter_by_role(raw_docs, user_role)[:top_k]

    documents = [
        {
            "id": doc.metadata.get("id", ""),
            "score": doc.metadata.get("confidence_score", 0.0),
            "metadata": doc.metadata,
            "text": doc.page_content,
        }
        for doc in filtered
    ]

    return {
        "query": query,
        "optimized_query": optimized,
        "vector_store_mode": mode,
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
    from langchain_core.documents import Document

    store, _ = _get_store()
    lc_docs = [
        Document(
            page_content=d.get("text", ""),
            metadata=d.get("metadata", d),
        )
        for d in documents
    ]
    store.add_documents(lc_docs)
    return {"upserted": len(lc_docs)}
