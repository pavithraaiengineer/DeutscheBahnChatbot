"""
RAG retriever — powered by LangChain.

Replaces the hand-rolled cosine-similarity retriever with:
  - LangChain PineconeVectorStore   (when PINECONE_API_KEY is set)
  - LangChain InMemoryVectorStore   (local fallback, no extra deps)
  - OpenAIEmbeddings / FakeEmbeddings
  - Role-based access control is preserved unchanged.
"""

from __future__ import annotations

from app.config import get_env
from app.rag.query_optimizer import optimize_query

# ---------------------------------------------------------------------------
# Role hierarchy (unchanged)
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
# Vector store bootstrap
# ---------------------------------------------------------------------------

def _build_vectorstore():
    """Return a LangChain VectorStore, Pinecone if configured else in-memory."""
    pinecone_key = get_env("PINECONE_API_KEY", "")
    openai_key = get_env("OPENAI_API_KEY", "")

    if openai_key:
        from langchain_openai import OpenAIEmbeddings
        embeddings = OpenAIEmbeddings(api_key=openai_key)
    else:
        from langchain_core.embeddings.fake import FakeEmbeddings
        embeddings = FakeEmbeddings(size=128)

    if pinecone_key:
        from langchain_pinecone import PineconeVectorStore
        index_name = get_env("PINECONE_INDEX", "debian-index")
        return PineconeVectorStore(index_name=index_name, embedding=embeddings), "pinecone"

    # Local in-memory fallback — seed from local_vector_store.json
    from langchain_core.vectorstores import InMemoryVectorStore
    store = InMemoryVectorStore(embedding=embeddings)
    _seed_in_memory(store)
    return store, "local"


def _seed_in_memory(store) -> None:
    """Load local_vector_store.json into the in-memory store."""
    import json
    from pathlib import Path
    from langchain_core.documents import Document

    path = Path("local_vector_store.json")
    if not path.exists():
        return

    raw = json.loads(path.read_text(encoding="utf-8"))
    docs = []
    for entry in raw.get("documents", raw) if isinstance(raw, dict) else raw:
        text = entry.get("text") or entry.get("metadata", {}).get("text", "")
        if text:
            docs.append(Document(page_content=text, metadata=entry.get("metadata", entry)))

    if docs:
        store.add_documents(docs)


_STORE = None
_STORE_MODE = "local"


def _get_store():
    global _STORE, _STORE_MODE
    if _STORE is None:
        _STORE, _STORE_MODE = _build_vectorstore()
    return _STORE, _STORE_MODE


# ---------------------------------------------------------------------------
# Public API (same signatures as before)
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

    # Fetch extra candidates so role filtering doesn't starve results
    raw_docs = store.similarity_search(optimized["optimized_query"], k=top_k * 3)
    filtered = _filter_by_role(raw_docs, user_role)[:top_k]

    # Normalise to the dict shape the rest of the app expects
    documents = [
        {
            "id": doc.metadata.get("id", ""),
            "score": doc.metadata.get("confidence_score", 0.0),
            "metadata": doc.metadata,
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
    return retrieve_context(query, language=language, top_k=top_k,
                            document_type=document_type, user_role=user_role)


def upsert_rag_documents(documents: list[dict]) -> dict:
    from langchain_core.documents import Document
    store, _ = _get_store()
    lc_docs = [
        Document(page_content=d.get("text", ""), metadata=d.get("metadata", d))
        for d in documents
    ]
    store.add_documents(lc_docs)
    return {"upserted": len(lc_docs)}
