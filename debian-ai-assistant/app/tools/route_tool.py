"""
Alternative route recommendation tool.

Production replacement:
- realtime route planner
- GTFS / DB Open Data
- user constraints: accessibility, family travel, luggage, bicycle
"""

from __future__ import annotations


def get_alternative_routes(origin: str, destination: str) -> dict:
    origin = origin or "current station"
    destination = destination or "destination"

    return {
        "origin": origin,
        "destination": destination,
        "recommendation_goal": "minimize delay impact",
        "alternatives": [
            {
                "type": "regional_train",
                "description": f"Take a regional connection from {origin} to {destination}.",
                "estimated_extra_minutes": 35,
                "confidence_score": 0.76,
            },
            {
                "type": "next_ice",
                "description": f"Use the next available ICE connection towards {destination}.",
                "estimated_extra_minutes": 55,
                "confidence_score": 0.71,
            },
            {
                "type": "human_support",
                "description": "Request human support for missed last connection, accessibility needs, or family travel.",
                "estimated_extra_minutes": None,
                "confidence_score": 0.88,
            },
        ],
    }
