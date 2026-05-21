"""
Cloud SQL / Firestore style session and claims store.

MVP:
- local JSON file fallback

Production:
- Firestore for sessions and claim status
- Cloud SQL for transactional claim records
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


STORE_PATH = Path("local_firestore_sessions.json")


def _load() -> dict:
    if not STORE_PATH.exists():
        return {"sessions": {}, "claims": {}}
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_session(session_id: str, payload: dict) -> dict:
    data = _load()
    data["sessions"][session_id] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    _save(data)
    return {"status": "saved", "session_id": session_id}


def save_claim(claim_id: str, payload: dict) -> dict:
    data = _load()
    data["claims"][claim_id] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    _save(data)
    return {"status": "saved", "claim_id": claim_id}


def get_store_status() -> dict:
    data = _load()
    return {
        "mode": "local_firestore_fallback",
        "sessions": len(data["sessions"]),
        "claims": len(data["claims"]),
    }
