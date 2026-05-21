"""
Security and governance.

Production:
- Secret Manager
- IAM
- Kubernetes RBAC
- Cloud DLP API
- Databricks Unity Catalog
- audit logs
- PII masking
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.tools.pii_masking_tool import mask_pii_text


LOG_DIR = Path("runtime_logs")
ANALYTICS_LOG = LOG_DIR / "analytics_events.jsonl"
EVAL_LOG = LOG_DIR / "evaluation_events.jsonl"
AUDIT_LOG = LOG_DIR / "audit_log.jsonl"


def ensure_log_dir() -> None:
    LOG_DIR.mkdir(exist_ok=True)


def sanitize_payload(payload: dict | None) -> dict:
    if not payload:
        return {}

    sanitized = {}
    for key, value in payload.items():
        if key.lower() in {"account_number", "iban", "db_api_key", "pinecone_api_key", "databricks_token"}:
            sanitized[key] = "***MASKED***"
        elif isinstance(value, str):
            sanitized[key] = mask_pii_text(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_payload(value)
        elif isinstance(value, list):
            sanitized[key] = [sanitize_payload(x) if isinstance(x, dict) else mask_pii_text(x) if isinstance(x, str) else x for x in value]
        else:
            sanitized[key] = value
    return sanitized


def write_jsonl(path: Path, payload: dict) -> None:
    ensure_log_dir()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_analytics_event(event_type: str, payload: dict) -> None:
    write_jsonl(
        ANALYTICS_LOG,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "payload": sanitize_payload(payload),
        },
    )


def write_evaluation_event(payload: dict) -> None:
    write_jsonl(
        EVAL_LOG,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": sanitize_payload(payload),
        },
    )


def write_audit_event(actor: str, action: str, resource: str, payload: dict | None = None) -> None:
    write_jsonl(
        AUDIT_LOG,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "resource": resource,
            "payload": sanitize_payload(payload or {}),
        },
    )


def governance_status() -> dict:
    return {
        "secret_management": "Secret Manager / Kubernetes Secrets in production; .env locally",
        "identity_access": "GCP IAM + Kubernetes RBAC",
        "data_governance": "Databricks Unity Catalog for governed lakehouse",
        "pii_protection": "IBAN/account masking and sanitized logs",
        "audit_logs": str(AUDIT_LOG),
        "analytics_logs": str(ANALYTICS_LOG),
        "evaluation_logs": str(EVAL_LOG),
    }
