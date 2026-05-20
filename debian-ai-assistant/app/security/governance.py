"""
Security and governance.

Production replacement:
- GCP IAM
- Secret Manager
- DLP API
- Databricks Unity Catalog
- audit logging
- BigQuery analytics
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.tools.pii_masking_tool import mask_pii_text


LOG_DIR = Path("runtime_logs")
ANALYTICS_LOG = LOG_DIR / "analytics_events.jsonl"
EVAL_LOG = LOG_DIR / "evaluation_events.jsonl"


def ensure_log_dir() -> None:
    LOG_DIR.mkdir(exist_ok=True)


def sanitize_payload(payload: dict) -> dict:
    sanitized = {}

    for key, value in payload.items():
        if isinstance(value, str):
            sanitized[key] = mask_pii_text(value)
        elif key in {"account_number", "iban"}:
            sanitized[key] = "***MASKED***"
        else:
            sanitized[key] = value

    return sanitized


def write_analytics_event(event_type: str, payload: dict) -> None:
    """
    MVP writes local JSONL.
    Production writes to BigQuery.
    """
    ensure_log_dir()
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "payload": sanitize_payload(payload),
    }
    with ANALYTICS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def write_evaluation_event(payload: dict) -> None:
    """
    MVP writes local JSONL.
    Production writes to a governed evaluation table.
    """
    ensure_log_dir()
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": sanitize_payload(payload),
    }
    with EVAL_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
