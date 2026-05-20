"""
Delay lookup tool.

MVP uses mock railway data.
Production replacement:
- DB Open Data / GTFS-RT / timetable API
- Databricks Gold table for historical delay facts
- Feature Store for delay prediction features
"""

from __future__ import annotations


MOCK_DELAY_DB = {
    "ICE 572": {
        "status": "delayed",
        "delay_minutes": 95,
        "planned_start_time": "2026-05-20T10:00:00",
        "actual_start_time": "2026-05-20T11:35:00",
        "origin": "Frankfurt(Main)Hbf",
        "destination": "Berlin Hbf",
        "platform": "7",
    },
    "ICE 999": {
        "status": "delayed",
        "delay_minutes": 140,
        "planned_start_time": "2026-05-20T08:00:00",
        "actual_start_time": "2026-05-20T10:20:00",
        "origin": "München Hbf",
        "destination": "Hamburg Hbf",
        "platform": "12",
    },
    "RE 50": {
        "status": "running",
        "delay_minutes": 15,
        "planned_start_time": "2026-05-20T09:00:00",
        "actual_start_time": "2026-05-20T09:15:00",
        "origin": "Hanau Hbf",
        "destination": "Frankfurt(Main)Hbf",
        "platform": "3",
    },
}


def normalize_train_number(train_number: str) -> str:
    return " ".join(train_number.upper().replace("-", " ").split())


def get_delay_status(train_number: str) -> dict:
    key = normalize_train_number(train_number)

    # Also support ICE572 style input.
    if key.startswith("ICE") and " " not in key:
        key = key.replace("ICE", "ICE ", 1)
    if key.startswith("RE") and " " not in key:
        key = key.replace("RE", "RE ", 1)

    result = MOCK_DELAY_DB.get(key)

    if not result:
        return {
            "train_number": train_number,
            "status": "unknown",
            "delay_minutes": None,
            "message": "No mock delay data found for this train. In production this calls the timetable API.",
        }

    return {"train_number": key, **result}
