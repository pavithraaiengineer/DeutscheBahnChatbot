"""
Databricks-style ETL pipeline.

Local MVP:
- writes Bronze/Silver/Gold JSONL files under data_lake/

Production mapping:
- Bronze Layer: raw DB Open Data, GTFS, delay logs, uploaded images, documents
- Silver Layer: cleaned station data, train schedules, delay events, passenger-rights docs
- Gold Layer: compensation eligibility, route recommendations, support analytics, delay prediction features
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


LAKE_ROOT = Path("data_lake")
BRONZE = LAKE_ROOT / "bronze"
SILVER = LAKE_ROOT / "silver"
GOLD = LAKE_ROOT / "gold"


RAW_DELAY_EVENTS = [
    {
        "train_number": "ICE 572",
        "route_id": "FRA-BER-ICE",
        "station_id": "8000105",
        "station_name": "Frankfurt(Main)Hbf",
        "planned_departure_time": "2026-05-20T10:00:00",
        "actual_departure_time": "2026-05-20T11:35:00",
        "historical_delay_minutes": 95,
        "weekday": "Wednesday",
        "weather_signal": "rain",
        "route_congestion_score": 0.72,
        "previous_station_delay": 30,
        "cancellation_flag": False,
        "ticket_price": 80.0,
    },
    {
        "train_number": "RE 50",
        "route_id": "HU-FRA-RE",
        "station_id": "8000150",
        "station_name": "Hanau Hbf",
        "planned_departure_time": "2026-05-20T09:00:00",
        "actual_departure_time": "2026-05-20T09:15:00",
        "historical_delay_minutes": 15,
        "weekday": "Wednesday",
        "weather_signal": "clear",
        "route_congestion_score": 0.22,
        "previous_station_delay": 5,
        "cancellation_flag": False,
        "ticket_price": 8.5,
    },
    {
        "train_number": "ICE 999",
        "route_id": "MUC-HAM-ICE",
        "station_id": "8000261",
        "station_name": "München Hbf",
        "planned_departure_time": "2026-05-20T08:00:00",
        "actual_departure_time": "2026-05-20T10:20:00",
        "historical_delay_minutes": 140,
        "weekday": "Wednesday",
        "weather_signal": "storm",
        "route_congestion_score": 0.91,
        "previous_station_delay": 85,
        "cancellation_flag": False,
        "ticket_price": 120.0,
    },
]


def ensure_dirs() -> None:
    for path in [BRONZE, SILVER, GOLD]:
        path.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def bronze_ingest() -> dict:
    ensure_dirs()
    timestamp = datetime.now(timezone.utc).isoformat()
    rows = [{**row, "_ingestion_timestamp": timestamp, "_source": "mock_db_gtfs_delay_feed"} for row in RAW_DELAY_EVENTS]
    output = BRONZE / "raw_delay_events.jsonl"
    write_jsonl(output, rows)
    return {"layer": "bronze", "rows": len(rows), "path": str(output)}


def silver_clean() -> dict:
    ensure_dirs()
    bronze_rows = read_jsonl(BRONZE / "raw_delay_events.jsonl")
    cleaned = []
    seen = set()

    for row in bronze_rows:
        key = (row["train_number"], row["station_id"], row["planned_departure_time"])
        if key in seen:
            continue
        seen.add(key)

        delay = int(row["historical_delay_minutes"])
        cleaned.append(
            {
                "train_number": row["train_number"].upper().strip(),
                "route_id": row["route_id"],
                "station_id": row["station_id"],
                "station_name": row["station_name"],
                "planned_departure_time": row["planned_departure_time"],
                "actual_departure_time": row["actual_departure_time"],
                "historical_delay_minutes": delay,
                "weekday": row["weekday"],
                "weather_signal": row["weather_signal"],
                "route_congestion_score": float(row["route_congestion_score"]),
                "previous_station_delay": int(row["previous_station_delay"]),
                "cancellation_flag": bool(row["cancellation_flag"]),
                "ticket_price": float(row["ticket_price"]),
                "is_delayed_60_plus": delay >= 60,
                "is_delayed_120_plus": delay >= 120,
            }
        )

    output = SILVER / "clean_delay_events.jsonl"
    write_jsonl(output, cleaned)
    return {"layer": "silver", "rows": len(cleaned), "path": str(output)}


def gold_features() -> dict:
    ensure_dirs()
    rows = read_jsonl(SILVER / "clean_delay_events.jsonl")
    feature_rows = []

    for row in rows:
        delay = int(row["historical_delay_minutes"])
        ticket_price = float(row["ticket_price"])

        if delay < 60:
            percentage = 0
            delay_risk = "low"
        elif delay < 120:
            percentage = 25
            delay_risk = "medium"
        else:
            percentage = 50
            delay_risk = "high"

        feature_rows.append(
            {
                "train_number": row["train_number"],
                "route_id": row["route_id"],
                "station_id": row["station_id"],
                "planned_departure_time": row["planned_departure_time"],
                "historical_delay_minutes": delay,
                "weekday": row["weekday"],
                "weather_signal": row["weather_signal"],
                "route_congestion_score": row["route_congestion_score"],
                "previous_station_delay": row["previous_station_delay"],
                "cancellation_flag": row["cancellation_flag"],
                "delay_risk_prediction": delay_risk,
                "compensation_percentage": percentage,
                "estimated_compensation_amount": round(ticket_price * percentage / 100, 2),
                "human_escalation_priority": "high" if delay >= 120 or row["cancellation_flag"] else "normal",
                "route_recommendation_needed": delay >= 60,
            }
        )

    output = GOLD / "delay_prediction_features.jsonl"
    write_jsonl(output, feature_rows)
    return {"layer": "gold", "rows": len(feature_rows), "path": str(output)}


def run_etl_pipeline() -> dict:
    return {
        "status": "completed",
        "pipeline": "debian_databricks_style_etl",
        "layers": [bronze_ingest(), silver_clean(), gold_features()],
        "production_mapping": {
            "bronze": "Raw DB Open Data, GTFS, delay logs, uploaded images, documents",
            "silver": "Cleaned station data, train schedules, delay events, passenger-rights docs",
            "gold": "Compensation eligibility, route recommendations, analytics, delay prediction features",
        },
    }


def read_feature_table() -> dict:
    return {
        "table": "gold.delay_prediction_features",
        "rows": read_jsonl(GOLD / "delay_prediction_features.jsonl"),
    }
