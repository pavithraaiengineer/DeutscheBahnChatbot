"""
Alternative route tool.

MVP returns mock alternatives.
Production replacement:
- timetable API
- route optimization service
- disruptions table
- user constraints such as accessibility, luggage, children, bicycle
"""

from __future__ import annotations


def get_alternative_routes(origin: str, destination: str) -> dict:
    origin = origin or "current station"
    destination = destination or "destination"

    return {
        "origin": origin,
        "destination": destination,
        "alternatives": [
            {
                "type": "regional_train",
                "description": f"Take a regional connection from {origin} to {destination}.",
                "estimated_extra_minutes": 35,
            },
            {
                "type": "next_ice",
                "description": f"Use the next available ICE connection towards {destination}.",
                "estimated_extra_minutes": 55,
            },
            {
                "type": "human_support",
                "description": "Request human support for special cases, accessibility, family travel, or missed last connection.",
                "estimated_extra_minutes": None,
            },
        ],
    }
