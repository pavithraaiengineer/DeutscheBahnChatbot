"""
Feature Store adapter.

MVP:
- reads local Gold feature table

Production:
- Databricks Feature Store / Unity Catalog feature table
- Online feature serving
"""

from __future__ import annotations

from app.databricks.etl_pipeline import read_feature_table


def get_delay_features(train_number: str) -> dict:
    normalized = train_number.upper().strip()
    table = read_feature_table()

    for row in table["rows"]:
        if row.get("train_number") == normalized:
            return {
                "found": True,
                "source": "local_gold_feature_table",
                "features": row,
                "use_cases": [
                    "Predict delay risk",
                    "Estimate compensation eligibility",
                    "Recommend alternative travel routes",
                    "Prioritize human escalation",
                ],
            }

    return {
        "found": False,
        "source": "local_gold_feature_table",
        "features": None,
    }
