"""
Journey planner tool for DeBian.

Strategy (in priority order):
1. DB Navigator public routing via db-vendo-client compatible endpoint
   (https://reiseauskunft.bahn.de/bin/query.exe/dn) — no auth needed.
2. If unreachable, generate a direct bahn.de search deep-link and
   return structured mock connections so the UI still works.

The public Hafas/Vendo endpoint returns JSON with connections,
departure/arrival times, products (ICE, IC, RE …) and prices.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

# ── Hafas / DB Navigator public endpoint ────────────────────────────
# This is the same backend used by the DB Navigator app.
HAFAS_BASE = "https://reiseauskunft.bahn.de/bin/query.exe/dn"

# ── known station Hafas IDs (fallback; EVA / IBNR is the same number) ──
STATION_IBNR: dict[str, str] = {
    "berlin hbf": "8011160",
    "hamburg hbf": "8002549",
    "münchen hbf": "8000261",
    "munich hbf": "8000261",
    "frankfurt(main)hbf": "8000105",
    "frankfurt hbf": "8000105",
    "köln hbf": "8000207",
    "cologne hbf": "8000207",
    "düsseldorf hbf": "8000085",
    "stuttgart hbf": "8000096",
    "hannover hbf": "8000152",
    "nürnberg hbf": "8000284",
    "leipzig hbf": "8010205",
    "dresden hbf": "8010085",
    "dortmund hbf": "8000080",
    "bremen hbf": "8000050",
    "mannheim hbf": "8000244",
    "karlsruhe hbf": "8000191",
    "augsburg hbf": "8000013",
    "erfurt hbf": "8010101",
    "hanau hbf": "8000150",
    "mainz hbf": "8000240",
    "kassel-wilhelmshöhe": "8003200",
}


def _resolve_ibnr(name: str) -> str | None:
    key = name.strip().lower()
    if key in STATION_IBNR:
        return STATION_IBNR[key]
    for k, v in STATION_IBNR.items():
        if key in k or k in key:
            return v
    return None


def _bahn_deeplink(origin: str, destination: str, dt: datetime) -> str:
    """Generate a bahn.de journey search deep-link."""
    date_str = dt.strftime("%d.%m.%Y")
    time_str = dt.strftime("%H:%M")
    params = urllib.parse.urlencode({
        "S": origin,
        "Z": destination,
        "date": date_str,
        "time": time_str,
        "start": "1",
        "MEId": "meform",
    })
    return f"https://www.bahn.de/buchung/fahrplan/suche?{params}"


def _mock_connections(origin: str, destination: str, dt: datetime) -> list[dict]:
    """Return 3 plausible mock connections when live API is unavailable."""
    base = dt.replace(second=0, microsecond=0)
    results = []
    offsets = [0, 60, 120]
    trains = [("ICE 572", "ICE", 189.0), ("IC 2123", "IC", 149.0), ("RE 1", "RE", 49.9)]
    for i, (offset, (train, product, price)) in enumerate(zip(offsets, trains)):
        dep = base + timedelta(minutes=offset + 10)
        travel_h = 2 if product == "ICE" else 3 if product == "IC" else 4
        arr = dep + timedelta(hours=travel_h)
        results.append({
            "connection_id": f"mock-{i + 1}",
            "departure": dep.strftime("%Y-%m-%dT%H:%M"),
            "arrival": arr.strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": travel_h * 60,
            "changes": 0,
            "products": [product],
            "trains": [train],
            "origin": origin,
            "destination": destination,
            "price_eur": price,
            "price_class": "2nd class",
            "source": "mock",
        })
    return results


def search_journeys(
    origin: str,
    destination: str,
    departure_datetime: str | None = None,
    num_results: int = 3,
) -> dict:
    """
    Search for train connections between origin and destination.

    Args:
        origin: Departure station name
        destination: Arrival station name
        departure_datetime: ISO datetime string (default: now + 30 min)
        num_results: Number of connections to return (max 5)

    Returns:
        dict with keys:
          - connections: list of connection dicts
          - booking_url: bahn.de deep link for booking
          - source: 'hafas', 'mock', or 'mock_fallback'
    """
    try:
        if departure_datetime:
            dt = datetime.fromisoformat(departure_datetime.replace("Z", "+00:00")).replace(tzinfo=None)
        else:
            dt = datetime.now() + timedelta(minutes=30)
    except Exception:
        dt = datetime.now() + timedelta(minutes=30)

    booking_url = _bahn_deeplink(origin, destination, dt)

    origin_id = _resolve_ibnr(origin)
    dest_id = _resolve_ibnr(destination)

    # Try Hafas live API
    if origin_id and dest_id:
        try:
            params = {
                "S": f"!{origin_id}",
                "Z": f"!{dest_id}",
                "date": dt.strftime("%d.%m.%y"),
                "time": dt.strftime("%H:%M"),
                "start": "1",
                "REQ0JourneyProduct_prod_list_1": "1111111111111111",
                "L": "vs_java3",
                "output": "json",
                "maxJourneys": str(num_results),
            }
            url = f"{HAFAS_BASE}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "DeBian-AI-Assistant/2.0",
                },
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                raw = json.loads(r.read().decode("utf-8"))

            connections = _parse_hafas(raw, origin, destination, num_results)
            if connections:
                return {
                    "source": "hafas",
                    "connections": connections,
                    "booking_url": booking_url,
                    "note": "Prices are indicative; confirm on bahn.de before booking.",
                }
        except Exception as err:
            pass  # fall through to mock

    # Mock fallback
    mocks = _mock_connections(origin, destination, dt)
    return {
        "source": "mock_fallback",
        "connections": mocks[:num_results],
        "booking_url": booking_url,
        "note": (
            "Live journey planner unavailable for this route. "
            "Click the booking URL to search on bahn.de."
        ),
    }


def _parse_hafas(raw: dict, origin: str, destination: str, limit: int) -> list[dict]:
    """Parse Hafas/Vendo JSON response into clean connection list."""
    trips = raw.get("Trip") or raw.get("journey") or []
    results = []

    for trip in trips[:limit]:
        legs = trip.get("LegList", {}).get("Leg") or trip.get("legs") or []
        if not legs:
            continue

        first_leg = legs[0] if isinstance(legs, list) else legs
        last_leg = legs[-1] if isinstance(legs, list) else legs

        dep_str = first_leg.get("dep", {}).get("time") or first_leg.get("departure", "")
        arr_str = last_leg.get("arr", {}).get("time") or last_leg.get("arrival", "")
        changes = max(0, len(legs) - 1) if isinstance(legs, list) else 0

        products = []
        trains = []
        for leg in (legs if isinstance(legs, list) else [legs]):
            product = (leg.get("product", {}) or {}).get("catOut", "").strip()
            num = (leg.get("product", {}) or {}).get("num", "").strip()
            if product:
                products.append(product)
            if num:
                trains.append(f"{product} {num}".strip())

        # Duration
        try:
            d = datetime.strptime(dep_str, "%H:%M:%S")
            a = datetime.strptime(arr_str, "%H:%M:%S")
            dur = int((a - d).total_seconds() / 60)
            if dur < 0:
                dur += 1440
        except Exception:
            dur = None

        price_raw = (trip.get("TariffResult") or {}).get("fareSetItem", [{}])
        price = None
        try:
            price = float(price_raw[0].get("fareItem", [{}])[0].get("price", 0)) / 100
        except Exception:
            pass

        results.append({
            "departure": dep_str,
            "arrival": arr_str,
            "duration_minutes": dur,
            "changes": changes,
            "products": list(set(products)),
            "trains": trains,
            "origin": origin,
            "destination": destination,
            "price_eur": price,
            "price_class": "2nd class",
            "source": "hafas",
        })

    return results


def get_ticket_classes() -> dict:
    """Return information about DB ticket classes and Bahncard discounts."""
    return {
        "classes": {
            "2nd": "Standard class — available on all trains",
            "1st": "First class — more space, quiet zones, complimentary drinks on ICE/IC",
        },
        "bahncard": {
            "bahncard_25": "25 % discount on flex fares",
            "bahncard_50": "50 % discount on flex fares",
            "bahncard_100": "All trains included — Germany-wide unlimited travel",
        },
        "ticket_types": {
            "Sparpreis": "Advance purchase saver — cheapest, non-refundable, seat binding",
            "Flexpreis": "Fully flexible — change/cancel free anytime",
            "Super Sparpreis": "Deepest discount — very early purchase, one specific train",
            "Deutschlandticket": "€58/month — all regional trains (RE, RB, S-Bahn), not ICE/IC",
        },
        "booking_channels": {
            "bahn.de": "Official website — full range of tickets and seat reservations",
            "DB Navigator app": "Mobile booking with digital ticket",
            "DB travel centres": "In-station booking counters",
        },
    }
