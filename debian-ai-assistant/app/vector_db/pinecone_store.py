"""
Pinecone vector DB with local fallback.

Documents:
- DB help documents
- Passenger-rights policy
- Compensation rules
- Station FAQs
- Ticket refund instructions
- Multilingual support articles
- Internal SOP documents

Metadata:
- language
- document_type
- region
- valid_from
- valid_to
- source_url
- confidence_score
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Iterable

from app.config import get_env, get_int_env


LOCAL_STORE_PATH = Path("local_vector_store.json")


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-ZÀ-ÿ0-9_]+", text.lower())


def hashing_embedding(text: str, dimension: int | None = None) -> list[float]:
    dimension = dimension or get_int_env("PINECONE_DIMENSION", 128)
    vector = [0.0] * dimension

    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % dimension
        vector[index] += 1.0

    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class VectorStore:
    def __init__(self) -> None:
        self.index_name = get_env("PINECONE_INDEX_NAME", "debian-rag")
        self.dimension = get_int_env("PINECONE_DIMENSION", 128)
        self.api_key = get_env("PINECONE_API_KEY", "")
        self.mode = "local"
        self._pinecone_index = None
        self._pinecone_error = None

        if self.api_key:
            try:
                from pinecone import Pinecone  # type: ignore
                pc = Pinecone(api_key=self.api_key)
                self._pinecone_index = pc.Index(self.index_name)
                self.mode = "pinecone"
            except Exception as error:
                self.mode = "local"
                self._pinecone_error = str(error)

    def upsert_documents(self, documents: Iterable[dict]) -> dict:
        docs = list(documents)

        if self.mode == "pinecone" and self._pinecone_index is not None:
            vectors = []
            for doc in docs:
                text = str(doc.get("text", ""))
                metadata = {k: v for k, v in doc.items() if k != "id"}
                metadata["text"] = text
                vectors.append(
                    {
                        "id": str(doc["id"]),
                        "values": hashing_embedding(text, self.dimension),
                        "metadata": metadata,
                    }
                )

            self._pinecone_index.upsert(vectors=vectors)
            return {"mode": "pinecone", "index": self.index_name, "upserted": len(vectors)}

        existing = self._load_local()
        for doc in docs:
            text = str(doc.get("text", ""))
            existing[str(doc["id"])] = {
                "document": doc,
                "vector": hashing_embedding(text, self.dimension),
            }

        self._save_local(existing)
        return {"mode": "local", "path": str(LOCAL_STORE_PATH), "upserted": len(docs)}

    def query(self, query_text: str, top_k: int = 3, metadata_filter: dict | None = None) -> dict:
        metadata_filter = metadata_filter or {}
        query_vector = hashing_embedding(query_text, self.dimension)

        if self.mode == "pinecone" and self._pinecone_index is not None:
            result = self._pinecone_index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
            )
            matches = []
            for match in result.get("matches", []):
                metadata = match.get("metadata", {})
                if not _metadata_matches(metadata, metadata_filter):
                    continue
                matches.append(
                    {
                        "id": match.get("id"),
                        "score": match.get("score"),
                        "metadata": metadata,
                    }
                )
            return {"mode": "pinecone", "matches": matches[:top_k]}

        local = self._load_local()
        scored = []
        for doc_id, item in local.items():
            doc = item["document"]
            if not _metadata_matches(doc, metadata_filter):
                continue
            score = cosine_similarity(query_vector, item["vector"])
            scored.append((score, doc_id, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return {
            "mode": "local",
            "matches": [
                {"id": doc_id, "score": round(score, 4), "metadata": doc}
                for score, doc_id, doc in scored[:top_k]
            ],
        }

    def _load_local(self) -> dict:
        if not LOCAL_STORE_PATH.exists():
            return {}
        return json.loads(LOCAL_STORE_PATH.read_text(encoding="utf-8"))

    def _save_local(self, payload: dict) -> None:
        LOCAL_STORE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _metadata_matches(metadata: dict, metadata_filter: dict) -> bool:
    for key, expected in metadata_filter.items():
        if expected is None:
            continue
        actual = metadata.get(key)
        if actual is not None and actual != expected:
            return False
    return True


def seed_default_documents() -> dict:
    docs = [
        {
            "id": "passenger_rights_en",
            "language": "en",
            "document_type": "passenger_rights",
            "region": "germany",
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
            "source_url": "internal://passenger-rights",
            "confidence_score": 0.95,
            "text": "For train delays, compensation may be available depending on delay duration, ticket price, and passenger-rights conditions.",
        },
        {
            "id": "passenger_rights_de",
            "language": "de",
            "document_type": "passenger_rights",
            "region": "germany",
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
            "source_url": "internal://fahrgastrechte",
            "confidence_score": 0.95,
            "text": "Bei Zugverspätungen kann abhängig von Dauer, Ticketpreis und Fahrgastrechten eine Entschädigung möglich sein.",
        },
        {
            "id": "refund_methods_en",
            "language": "en",
            "document_type": "refund",
            "region": "germany",
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
            "source_url": "internal://refund-methods",
            "confidence_score": 0.92,
            "text": "Refunds can be processed to a bank account or as a voucher. Account numbers must be masked and only the last four digits should be displayed.",
        },
        {
            "id": "station_faq_en",
            "language": "en",
            "document_type": "station_faq",
            "region": "germany",
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
            "source_url": "internal://station-faq",
            "confidence_score": 0.89,
            "text": "Station FAQs answer questions about platforms, alternative routes, accessibility, luggage, and service points.",
        },
        {
            "id": "internal_sop_handoff_en",
            "language": "en",
            "document_type": "internal_sop",
            "region": "germany",
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
            "source_url": "internal://human-handoff-sop",
            "confidence_score": 0.91,
            "text": "Escalate to human support when the user requests a callback, needs accessibility support, or the automated flow is insufficient.",
        },
    ]
    return VectorStore().upsert_documents(docs)
