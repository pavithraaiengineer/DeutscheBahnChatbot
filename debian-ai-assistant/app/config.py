"""
Config loader for DeBian.

Local:
- reads .env without external dependencies

Production:
- secrets should come from Secret Manager / Kubernetes Secret / Workload Identity
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env(env_file: str = ".env") -> None:
    path = Path(env_file)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


load_env()


def get_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def get_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def config_status() -> dict:
    return {
        "env": get_env("ENV", "local"),
        "db_timetables_configured": bool(get_env("DB_CLIENT_ID") and get_env("DB_API_KEY")),
        "pinecone_configured": bool(get_env("PINECONE_API_KEY")),
        "databricks_configured": bool(get_env("DATABRICKS_HOST") and get_env("DATABRICKS_TOKEN")),
        "gcp_project_configured": bool(get_env("GCP_PROJECT_ID")),
        "bigquery_dataset": get_env("BIGQUERY_DATASET", "debian_analytics"),
        "gcs_bucket_configured": bool(get_env("GCS_BUCKET")),
    }
