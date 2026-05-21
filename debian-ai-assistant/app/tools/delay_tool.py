"""
Delay lookup tool.

Modes:
1. Real-time DB Timetables API if DB_CLIENT_ID + DB_API_KEY + station are available.
2. Mock fallback so the demo remains stable.

For real-time DB timetable APIs, station name is required because the API is station-board based.
"""

from __future__ import annotations

import os
import re
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime

from app.config import get_env


DB_API_BASE = get_env(
    "DB_TIMETABLES_BASE_URL",
    "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1",
)
DB_CLIENT_ID = get_env("DB_CLIENT_ID", "")
DB_API_KEY = get_env("DB_API_KEY", "")


MOCK_DELAY_DB = {
    "ICE 572": {
        "source": "mock",
        "status": "delayed",
        "delay_minutes": 95,
        "planned_start_time": "2026-05-20T10:00:00",
        "actual_start_time": "2026-05-20T11:35:00",
        "origin": "Frankfurt(Main)Hbf",
        "destination": "Berlin Hbf",
        "station_name": "Frankfurt(Main)Hbf",
        "platform": "7",
    },
    "ICE 999": {
        "source": "mock",
        "status": "delayed",
        "delay_minutes": 140,
        "planned_start_time": "2026-05-20T08:00:00",
        "actual_start_time": "2026-05-20T10:20:00",
        "origin": "München Hbf",
        "destination": "Hamburg Hbf",
        "station_name": "München Hbf",
        "platform": "12",
    },
    "RE 50": {
        "source": "mock",
        "status": "running",
        "delay_minutes": 15,
        "planned_start_time": "2026-05-20T09:00:00",
        "actual_start_time": "2026-05-20T09:15:00",
        "origin": "Hanau Hbf",
        "destination": "Frankfurt(Main)Hbf",
        "station_name": "Hanau Hbf",
        "platform": "3",
    },
}


def normalize_train_number(train_number: str) -> str:
    value = " ".join(str(train_number).upper().replace("-", " ").split())
    match = re.match(r"^([A-Z]+)\s*(\d+)$", value)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return value


def get_delay_status(
    train_number: str,
    station_name: str | None = None,
    planned_start_time: str | None = None,
) -> dict:
    if station_name and DB_CLIENT_ID and DB_API_KEY:
        return get_realtime_delay_status(
            station_name=station_name,
            train_number=train_number,
            planned_start_time=planned_start_time,
            fallback_to_mock=True,
        )

    result = get_mock_delay_status(train_number)
    if station_name:
        result["station_name_requested"] = station_name
    result["real_time_ready"] = bool(DB_CLIENT_ID and DB_API_KEY)
    return result


def get_mock_delay_status(train_number: str) -> dict:
    key = normalize_train_number(train_number)
    result = MOCK_DELAY_DB.get(key)

    if not result:
        return {
            "train_number": train_number,
            "source": "mock",
            "status": "unknown",
            "delay_minutes": None,
            "message": "No mock delay data found. Configure DB API keys and provide station_name for real-time mode.",
        }

    return {"train_number": key, **result}


def get_realtime_delay_status(
    station_name: str,
    train_number: str,
    planned_start_time: str | None = None,
    fallback_to_mock: bool = True,
) -> dict:
    try:
        station = find_station(station_name)
        normalized_train = normalize_train_number(train_number)
        target_dt = _parse_requested_datetime(planned_start_time) or datetime.now()
        date_str = target_dt.strftime("%y%m%d")
        hour_str = target_dt.strftime("%H")

        planned_xml = _api_get_xml(f"/plan/{station['eva_no']}/{date_str}/{hour_str}")
        planned_stops = _parse_stops(planned_xml)
        matched = _find_train_stop(planned_stops, normalized_train)

        if matched is None:
            return {
                "source": "db_timetables_api",
                "train_number": normalized_train,
                "station_name": station["name"],
                "station_eva_no": station["eva_no"],
                "status": "not_found",
                "delay_minutes": None,
                "message": "Train not found in selected station/hour timetable.",
            }

        changes_xml = _get_combined_changes(station["eva_no"])
        changed_stops = _parse_stops(changes_xml)
        changed = changed_stops.get(matched["id"])
        merged = _merge_planned_and_changed_stop(matched, changed)

        delay_minutes = _calculate_delay_minutes(merged.get("planned_time"), merged.get("actual_time"))
        status = "cancelled" if merged.get("cancelled") else "delayed" if delay_minutes and delay_minutes >= 60 else "running"

        return {
            "source": "db_timetables_api",
            "train_number": normalized_train,
            "station_name": station["name"],
            "station_eva_no": station["eva_no"],
            "status": status,
            "delay_minutes": delay_minutes,
            "planned_start_time": _dt_to_iso(merged.get("planned_time")),
            "actual_start_time": _dt_to_iso(merged.get("actual_time")),
            "planned_platform": merged.get("planned_platform"),
            "actual_platform": merged.get("actual_platform"),
            "direction": merged.get("direction"),
            "stop_id": matched["id"],
        }

    except Exception as error:
        if fallback_to_mock:
            fallback = get_mock_delay_status(train_number)
            fallback["source"] = "mock_fallback_after_realtime_error"
            fallback["real_time_error"] = str(error)
            return fallback
        raise


def find_station(station_name: str) -> dict:
    xml_text = _api_get_xml(f"/station/{urllib.parse.quote(station_name.strip())}")
    root = ET.fromstring(xml_text)

    stations = []
    for station in root.iter("station"):
        name = station.attrib.get("name")
        eva_no = station.attrib.get("eva") or station.attrib.get("evaNo")
        if name and eva_no:
            stations.append({"name": name, "eva_no": eva_no})

    if not stations:
        raise ValueError(f"No station found for {station_name}")

    exact = [s for s in stations if s["name"].lower() == station_name.lower()]
    return exact[0] if exact else stations[0]


def _api_get_xml(path: str) -> str:
    request = urllib.request.Request(
        f"{DB_API_BASE}{path}",
        headers={
            "DB-Client-Id": DB_CLIENT_ID,
            "DB-Api-Key": DB_API_KEY,
            "Accept": "application/xml",
            "User-Agent": "DeBian-AI-Assistant/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"DB API HTTP {error.code}: {body[:250]}") from error


def _get_combined_changes(eva_no: str) -> str:
    try:
        return _api_get_xml(f"/fchg/{eva_no}")
    except Exception:
        return _api_get_xml(f"/rchg/{eva_no}")


def _parse_stops(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    stops = {}

    for stop in root.iter("s"):
        stop_id = stop.attrib.get("id")
        if not stop_id:
            continue

        tl = stop.find("tl")
        ar = stop.find("ar")
        dp = stop.find("dp")
        event = dp if dp is not None else ar

        train_class = tl.attrib.get("c") if tl is not None else ""
        train_number = tl.attrib.get("n") if tl is not None else ""
        line = normalize_train_number(f"{train_class} {train_number}".strip())

        planned_time = _parse_db_time(event.attrib.get("pt")) if event is not None else None
        actual_time = _parse_db_time(event.attrib.get("ct")) if event is not None else None
        planned_platform = event.attrib.get("pp") if event is not None else None
        actual_platform = event.attrib.get("cp") if event is not None else None
        cancelled = event is not None and (event.attrib.get("cs") == "c" or event.attrib.get("clt") == "c")

        direction = None
        if dp is not None:
            direction = dp.attrib.get("l") or dp.attrib.get("ppth")
        if not direction and ar is not None:
            direction = ar.attrib.get("ppth")

        stops[stop_id] = {
            "id": stop_id,
            "line": line,
            "planned_time": planned_time,
            "actual_time": actual_time,
            "planned_platform": planned_platform,
            "actual_platform": actual_platform,
            "cancelled": cancelled,
            "direction": direction,
        }

    return stops


def _find_train_stop(stops: dict, train_number: str) -> dict | None:
    target = normalize_train_number(train_number)
    target_compact = target.replace(" ", "")

    for stop in stops.values():
        line = normalize_train_number(stop.get("line", ""))
        if line == target or line.replace(" ", "") == target_compact:
            return stop

    return None


def _merge_planned_and_changed_stop(planned: dict, changed: dict | None) -> dict:
    merged = dict(planned)
    if changed:
        for key, value in changed.items():
            if value not in {None, ""}:
                merged[key] = value

    if merged.get("actual_time") is None:
        merged["actual_time"] = merged.get("planned_time")
    if merged.get("actual_platform") is None:
        merged["actual_platform"] = merged.get("planned_platform")

    return merged


def _parse_db_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%y%m%d%H%M")


def _parse_requested_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _calculate_delay_minutes(planned: datetime | None, actual: datetime | None) -> int | None:
    if not planned or not actual:
        return None
    return int(round((actual - planned).total_seconds() / 60))


def _dt_to_iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="minutes") if value else None
