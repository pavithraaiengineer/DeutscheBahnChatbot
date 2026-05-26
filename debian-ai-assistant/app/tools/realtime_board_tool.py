"""
Real-time departure / arrival board tool.

Uses the public bahnhof.de board API (no credentials required).
Falls back to mock data when the API is unreachable.

Public endpoint:
  GET https://www.bahnhof.de/api/boards/departures
      ?evaNumbers=<EVA>
      &duration=<minutes>
      &locale=<de|en>

EVA numbers are looked up via the DB Timetables station search
when DB_CLIENT_ID + DB_API_KEY are configured, otherwise a
built-in offline lookup table is used.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

from app.config import get_env

# ── offline EVA table (top 30 German stations) ────────────────────────
STATION_EVA: dict[str, str] = {
    "berlin hbf": "8011160",
    "berlin hauptbahnhof": "8011160",
    "hamburg hbf": "8002549",
    "hamburg hauptbahnhof": "8002549",
    "münchen hbf": "8000261",
    "munich hbf": "8000261",
    "frankfurt(main)hbf": "8000105",
    "frankfurt main hbf": "8000105",
    "frankfurt hbf": "8000105",
    "köln hbf": "8000207",
    "cologne hbf": "8000207",
    "düsseldorf hbf": "8000085",
    "stuttgart hbf": "8000096",
    "hannover hbf": "8000152",
    "nürnberg hbf": "8000284",
    "nuremberg hbf": "8000284",
    "leipzig hbf": "8010205",
    "dresden hbf": "8010085",
    "dortmund hbf": "8000080",
    "essen hbf": "8000098",
    "bremen hbf": "8000050",
    "hannover": "8000152",
    "mannheim hbf": "8000244",
    "karlsruhe hbf": "8000191",
    "augsburg hbf": "8000013",
    "wiesbaden hbf": "8000250",
    "mainz hbf": "8000240",
    "freiburg(breisgau) hbf": "8000107",
    "kassel-wilhelmshöhe": "8003200",
    "erfurt hbf": "8010101",
    "hanau hbf": "8000150",
    "offenburg": "8000290",
}

BOARD_BASE = "https://www.bahnhof.de/api/boards"


def _resolve_eva(station_name: str) -> str | None:
    """Return EVA number for a station name, using offline table first."""
    key = station_name.strip().lower()
    if key in STATION_EVA:
        return STATION_EVA[key]
    # partial match
    for k, v in STATION_EVA.items():
        if key in k or k in key:
            return v
    # Try live DB Timetables API if credentials exist
    try:
        from app.tools.delay_tool import find_station, DB_CLIENT_ID, DB_API_KEY
        if DB_CLIENT_ID and DB_API_KEY:
            s = find_station(station_name)
            return s.get("eva_no")
    except Exception:
        pass
    return None


def _board_request(endpoint: str, eva: str, duration: int = 60, locale: str = "en") -> dict:
    """Call bahnhof.de board API and return parsed JSON."""
    url = (
        f"{BOARD_BASE}/{endpoint}"
        f"?evaNumbers={eva}&duration={duration}&locale={locale}"
        f"&modeOfTransport=HIGH_SPEED_TRAIN,INTER_REGIONAL_TRAIN,REGIONAL_TRAIN,CITY_TRAIN"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "DeBian-AI-Assistant/2.0",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def _parse_entry(entry: dict, kind: str) -> dict:
    """Normalise a raw board entry into a clean dict."""
    time_key = "departure" if kind == "departure" else "arrival"
    time_block = entry.get(time_key, {}) or {}
    scheduled = time_block.get("scheduledTime", "")
    actual = time_block.get("time", scheduled)
    delay_min = time_block.get("delay") or 0
    platform_sched = (entry.get("track") or {}).get("scheduled", "?")
    platform_actual = (entry.get("track") or {}).get("actual", platform_sched)
    cancelled = entry.get("cancelled", False)

    transport = entry.get("transport", {}) or {}
    train_name = (
        (transport.get("category", "") or "") + " " + str(transport.get("number", "") or "")
    ).strip()

    via = []
    for stop in (entry.get("stops") or [])[:5]:
        n = (stop.get("station") or {}).get("name", "")
        if n:
            via.append(n)

    final_dest = (entry.get("destination") or {}).get("name", "") or (via[-1] if via else "")
    origin_name = (entry.get("origin") or {}).get("name", "") or (via[0] if via else "")

    return {
        "train": train_name,
        "direction" if kind == "departure" else "from": final_dest if kind == "departure" else origin_name,
        "scheduled_time": scheduled[:16] if scheduled else None,
        "actual_time": actual[:16] if actual else None,
        "delay_minutes": int(delay_min),
        "platform_scheduled": platform_sched,
        "platform_actual": platform_actual,
        "cancelled": cancelled,
        "via": via,
    }


# ── MOCK DATA ─────────────────────────────────────────────────────────

def _mock_departures(station_name: str) -> dict:
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%dT%H:%M")
    return {
        "source": "mock",
        "station": station_name,
        "board_type": "departures",
        "generated_at": now_str,
        "entries": [
            {
                "train": "ICE 572",
                "direction": "Berlin Hbf",
                "scheduled_time": now_str,
                "actual_time": now_str,
                "delay_minutes": 0,
                "platform_scheduled": "7",
                "platform_actual": "7",
                "cancelled": False,
                "via": ["Erfurt Hbf", "Leipzig Hbf"],
            },
            {
                "train": "ICE 999",
                "direction": "Hamburg Hbf",
                "scheduled_time": now_str,
                "actual_time": now_str,
                "delay_minutes": 15,
                "platform_scheduled": "12",
                "platform_actual": "12",
                "cancelled": False,
                "via": ["Hannover Hbf"],
            },
            {
                "train": "RE 50",
                "direction": "Hanau Hbf",
                "scheduled_time": now_str,
                "actual_time": now_str,
                "delay_minutes": 0,
                "platform_scheduled": "3",
                "platform_actual": "3",
                "cancelled": False,
                "via": [],
            },
        ],
        "message": "Live API unavailable — using demo data. Configure station EVA or DB credentials for real-time boards.",
    }


# ── PUBLIC FUNCTIONS ──────────────────────────────────────────────────

def get_departures(
    station_name: str,
    duration_minutes: int = 120,
    locale: str = "en",
) -> dict:
    """
    Return upcoming departures for a station.

    Args:
        station_name: Human-readable station name (e.g. 'Frankfurt(Main)Hbf')
        duration_minutes: Look-ahead window (default 120 min)
        locale: 'en' or 'de'

    Returns:
        dict with keys: source, station, board_type, generated_at, entries[]
    """
    eva = _resolve_eva(station_name)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")

    if not eva:
        return {
            "source": "mock",
            "station": station_name,
            "board_type": "departures",
            "generated_at": now_str,
            "entries": [],
            "error": f"Station '{station_name}' not found in lookup table. Try a major German station name.",
        }

    try:
        raw = _board_request("departures", eva, duration_minutes, locale)
        entries = [_parse_entry(e, "departure") for e in (raw.get("entries") or raw.get("departures") or [])]
        return {
            "source": "bahnhof.de",
            "station": station_name,
            "eva_number": eva,
            "board_type": "departures",
            "generated_at": now_str,
            "entries": entries[:20],
        }
    except Exception as exc:
        fallback = _mock_departures(station_name)
        fallback["live_error"] = str(exc)
        return fallback


def get_arrivals(
    station_name: str,
    duration_minutes: int = 120,
    locale: str = "en",
) -> dict:
    """
    Return upcoming arrivals for a station.
    """
    eva = _resolve_eva(station_name)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")

    if not eva:
        return {
            "source": "mock",
            "station": station_name,
            "board_type": "arrivals",
            "generated_at": now_str,
            "entries": [],
            "error": f"Station '{station_name}' not found.",
        }

    try:
        raw = _board_request("arrivals", eva, duration_minutes, locale)
        entries = [_parse_entry(e, "arrival") for e in (raw.get("entries") or raw.get("arrivals") or [])]
        return {
            "source": "bahnhof.de",
            "station": station_name,
            "eva_number": eva,
            "board_type": "arrivals",
            "generated_at": now_str,
            "entries": entries[:20],
        }
    except Exception as exc:
        return {
            "source": "mock",
            "station": station_name,
            "board_type": "arrivals",
            "generated_at": now_str,
            "entries": [],
            "live_error": str(exc),
            "message": "Live API unavailable.",
        }
