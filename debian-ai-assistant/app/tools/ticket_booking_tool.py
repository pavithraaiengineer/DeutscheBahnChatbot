"""
Ticket booking assistant tool for DeBian.

DeBian cannot issue real tickets (that requires a licensed DB reseller
agreement), but it can:

1. Collect journey details from the user in a multi-step wizard.
2. Recommend the best ticket type for their situation.
3. Generate a pre-filled bahn.de deep link they click to complete booking.
4. Explain Bahncard, seat reservation, and group/bike tickets.

This module handles steps 1–4 so the agent can guide passengers
end-to-end without needing backend credentials.
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime, timedelta


# ── Booking URL builders ─────────────────────────────────────────────

def build_bahn_booking_url(
    origin: str,
    destination: str,
    departure_date: str,
    departure_time: str,
    passengers: int = 1,
    travel_class: int = 2,
    with_bahncard: bool = False,
    bahncard_type: str = "25",
    bike: bool = False,
) -> str:
    """
    Build a bahn.de journey search URL pre-filled with journey details.

    The user can click this link to complete the booking on bahn.de.
    """
    params: dict[str, str] = {
        "S": origin,
        "Z": destination,
        "date": departure_date,  # DD.MM.YYYY
        "time": departure_time,  # HH:MM
        "start": "1",
        "MEId": "meform",
        "REQ0JourneyStopsS0G": origin,
        "REQ0JourneyStopsZ0G": destination,
    }

    if passengers > 1:
        params["REQ0Tariff_TravellerAge.1"] = "35"
        for i in range(2, min(passengers + 1, 6)):
            params[f"REQ0Tariff_TravellerAge.{i}"] = "35"

    if travel_class == 1:
        params["REQ0JourneyProduct_prod_list_1"] = "1111111111111111"
        params["travell_class"] = "1"

    if with_bahncard:
        params[f"REQ0Tariff_TravellerReductionClass.1"] = (
            "2" if bahncard_type == "25" else "4" if bahncard_type == "50" else "8"
        )

    if bike:
        params["REQ0JourneyProduct_opt_bike"] = "1"

    return f"https://www.bahn.de/buchung/fahrplan/suche?{urllib.parse.urlencode(params)}"


def build_seat_reservation_url(train_number: str, departure_date: str) -> str:
    """Deep link to DB seat reservation for a specific train."""
    params = {
        "zugNummer": train_number.replace(" ", ""),
        "abfahrtsDatum": departure_date,
    }
    return f"https://www.bahn.de/buchung/sitzplatz?{urllib.parse.urlencode(params)}"


# ── Ticket recommendation engine ─────────────────────────────────────

def recommend_ticket(
    days_in_advance: int,
    is_flexible: bool,
    frequency: str,  # "once", "occasional", "regular"
    travel_class: int = 2,
    has_bahncard: bool = False,
    is_group: bool = False,
    budget_eur: float | None = None,
) -> dict:
    """
    Recommend the best DB ticket type based on travel context.

    Returns a dict with:
      - recommended_ticket: name of the best ticket
      - reason: plain-language explanation
      - alternatives: list of other options
      - booking_tips: list of actionable tips
    """
    recommendations = []
    tips = []
    primary = None
    reason = ""

    # Group travel
    if is_group and not has_bahncard:
        primary = "Gruppen-Sparpreis / Group saver"
        reason = (
            "For 6+ people travelling together, the Group saver (Gruppen-Sparpreis) "
            "offers significant savings — from €19.90 per person on long-distance trains."
        )
        tips.append("Book at least 3 days ahead for group fares.")
        recommendations = ["DB Group Ticket", "Quer-durchs-Land-Ticket (regional groups)"]

    # Regular traveller → Bahncard
    elif frequency == "regular" and not has_bahncard:
        primary = "Bahncard 50"
        reason = (
            "As a regular traveller, the Bahncard 50 pays for itself quickly — "
            "it gives 50 % off all flex fares and 25 % off Sparpreis fares."
        )
        tips.append("Bahncard 50 2nd class costs €244/year; it breaks even after ~€500 of full-price fares.")
        recommendations = ["Bahncard 25 (€62.90/year)", "Bahncard 100 (€4,294/year — unlimited)"]

    # Advance flexible booking
    elif days_in_advance >= 14 and is_flexible:
        primary = "Sparpreis"
        reason = (
            "Booking 14+ days in advance, the Sparpreis is the best value — "
            "from €17.90 and refundable (with a €10 fee) before departure."
        )
        tips.append("Set a fare alert on bahn.de — prices change as trains fill up.")
        recommendations = ["Super Sparpreis (cheaper, non-refundable)", "Flexpreis (fully flexible)"]

    # Very early booking, price-sensitive
    elif days_in_advance >= 60 and not is_flexible:
        primary = "Super Sparpreis"
        reason = (
            "Booked 60+ days ahead with no need to change plans, the Super Sparpreis "
            "is the cheapest DB long-distance option — from €17.90 on many routes."
        )
        tips.append("Super Sparpreis cannot be refunded but can be upgraded to Sparpreis for €10.")
        recommendations = ["Sparpreis (small premium, more flexibility)"]

    # Last-minute / flexible
    elif is_flexible or days_in_advance <= 3:
        primary = "Flexpreis"
        reason = (
            "For last-minute or flexible trips, the Flexpreis lets you take any train "
            "on the day and change / cancel free of charge."
        )
        if has_bahncard:
            reason += " With your Bahncard, you get an additional 25–50 % off."
        recommendations = ["Sparpreis (cheaper if your plans are firm)"]

    # General medium-advance
    else:
        primary = "Sparpreis"
        reason = (
            "The Sparpreis is the right balance of price and flexibility "
            "for most journeys booked 3–14 days ahead."
        )
        recommendations = ["Super Sparpreis (cheaper, non-refundable)", "Flexpreis (fully flexible, more expensive)"]

    # Class 1 note
    if travel_class == 1:
        tips.append(
            "1st class adds ~55 % to the base fare but includes more space, "
            "quiet zones, and complimentary drinks on ICE/IC trains."
        )

    # Deutschlandticket note for regional
    tips.append(
        "For regional-only travel (RE, RB, S-Bahn), consider the Deutschlandticket "
        "(€58/month) — it covers all regional trains across Germany."
    )

    return {
        "recommended_ticket": primary,
        "reason": reason,
        "alternatives": recommendations,
        "booking_tips": tips,
    }


# ── Guided booking state machine helpers ─────────────────────────────

BOOKING_STEPS = [
    "origin",
    "destination",
    "travel_date",
    "travel_time",
    "passengers",
    "travel_class",
    "flexibility",
    "bahncard",
    "bike",
    "confirm",
]


def next_booking_prompt(step: str, lang: str = "en") -> str:
    """Return the question to ask the user at each booking step."""
    prompts = {
        "en": {
            "origin":       "Where are you travelling FROM?\nExample: Frankfurt(Main)Hbf",
            "destination":  "Where are you travelling TO?\nExample: Berlin Hbf",
            "travel_date":  "What date do you want to travel?\nExample: 27.05.2026 or tomorrow",
            "travel_time":  "What time do you want to depart? (24h format)\nExample: 09:30",
            "passengers":   "How many passengers? (1–5)\nExample: 1",
            "travel_class": "Which class?\n1 = First class  |  2 = Second class (default)",
            "flexibility":  "Do you need a flexible ticket you can change/cancel?\nType: yes or no",
            "bahncard":     "Do you have a Bahncard?\nType: none, 25, 50, or 100",
            "bike":         "Do you want to bring a bicycle?\nType: yes or no",
            "confirm":      "✅ I have all the details. Shall I generate your booking link?\nType: yes to confirm",
        },
        "de": {
            "origin":       "Wo reisen Sie AB?\nBeispiel: Frankfurt(Main)Hbf",
            "destination":  "Wohin reisen Sie?\nBeispiel: Berlin Hbf",
            "travel_date":  "An welchem Datum möchten Sie reisen?\nBeispiel: 27.05.2026 oder morgen",
            "travel_time":  "Um wie viel Uhr möchten Sie abfahren?\nBeispiel: 09:30",
            "passengers":   "Wie viele Passagiere? (1–5)\nBeispiel: 1",
            "travel_class": "Welche Klasse?\n1 = Erste Klasse  |  2 = Zweite Klasse (Standard)",
            "flexibility":  "Benötigen Sie ein flexibles Ticket?\nEingabe: ja oder nein",
            "bahncard":     "Haben Sie eine Bahncard?\nEingabe: keine, 25, 50 oder 100",
            "bike":         "Möchten Sie ein Fahrrad mitnehmen?\nEingabe: ja oder nein",
            "confirm":      "✅ Ich habe alle Details. Soll ich Ihren Buchungslink erstellen?\nEingabe: ja",
        },
    }
    lang_map = prompts.get(lang, prompts["en"])
    return lang_map.get(step, "Please provide the required information.")


def mask_iban(raw: str) -> str:
    """
    Mask an IBAN for safe display.
    Shows country code + check digits (first 4 chars) + stars + last 4 digits.
    Example: DE89370400440532013000 → DE89 ************** 3000
    """
    clean = raw.replace(" ", "").upper()
    if len(clean) < 8:
        return "*" * len(clean)
    prefix = clean[:4]        # country code + check digits (e.g. DE89)
    last4  = clean[-4:]       # last 4 digits always visible
    stars  = "*" * (len(clean) - 8)
    return f"{prefix} {stars} {last4}"


def build_booking_summary(booking: dict, lang: str = "en") -> dict:
    """
    Given a completed booking dict, return summary + booking URL + ticket recommendation.
    """
    origin = booking.get("origin", "")
    destination = booking.get("destination", "")
    travel_date = booking.get("travel_date", "")
    travel_time = booking.get("travel_time", "09:00")
    passengers = int(booking.get("passengers", 1))
    travel_class = int(booking.get("travel_class", 2))
    flexible = booking.get("flexibility", "no").lower() in ("yes", "ja", "y")
    bahncard = booking.get("bahncard", "none").strip()
    has_bahncard = bahncard not in ("none", "keine", "no", "nein", "")
    bahncard_type = bahncard if has_bahncard else "25"
    bike = booking.get("bike", "no").lower() in ("yes", "ja", "y")

    # Normalise date
    dt_today = datetime.now()
    raw_date = travel_date.strip().lower()
    if raw_date in ("today", "heute"):
        date_obj = dt_today
    elif raw_date in ("tomorrow", "morgen"):
        date_obj = dt_today + timedelta(days=1)
    else:
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                date_obj = datetime.strptime(travel_date.strip(), fmt)
                break
            except ValueError:
                pass
        else:
            date_obj = dt_today + timedelta(days=1)

    days_ahead = max(0, (date_obj - dt_today).days)
    date_str = date_obj.strftime("%d.%m.%Y")

    booking_url = build_bahn_booking_url(
        origin=origin,
        destination=destination,
        departure_date=date_str,
        departure_time=travel_time,
        passengers=passengers,
        travel_class=travel_class,
        with_bahncard=has_bahncard,
        bahncard_type=bahncard_type,
        bike=bike,
    )

    seat_url = build_seat_reservation_url(
        train_number="",
        departure_date=date_str,
    )

    recommendation = recommend_ticket(
        days_in_advance=days_ahead,
        is_flexible=flexible,
        frequency="once",
        travel_class=travel_class,
        has_bahncard=has_bahncard,
        is_group=passengers >= 6,
    )

    summary_lines = {
        "en": [
            f"🚆 Journey: {origin} → {destination}",
            f"📅 Date: {date_str} at {travel_time}",
            f"👥 Passengers: {passengers}",
            f"🎫 Class: {'1st' if travel_class == 1 else '2nd'}",
            f"🚴 Bike: {'yes' if bike else 'no'}",
            f"💳 Bahncard: {bahncard if has_bahncard else 'none'}",
        ],
        "de": [
            f"🚆 Verbindung: {origin} → {destination}",
            f"📅 Datum: {date_str} um {travel_time} Uhr",
            f"👥 Reisende: {passengers}",
            f"🎫 Klasse: {'1.' if travel_class == 1 else '2.'}",
            f"🚴 Fahrrad: {'ja' if bike else 'nein'}",
            f"💳 Bahncard: {bahncard if has_bahncard else 'keine'}",
        ],
    }

    lang_key = lang if lang in summary_lines else "en"

    # IBAN — mask it before storing in the response
    raw_iban = booking.get("iban", "").strip()
    masked_iban = mask_iban(raw_iban) if raw_iban else ""
    last4 = raw_iban.replace(" ", "")[-4:] if len(raw_iban.replace(" ", "")) >= 4 else ""

    # Append IBAN line to summary if provided
    if masked_iban:
        summary_lines["en"].append(f"💳 Payment IBAN: {masked_iban} (****{last4})")
        summary_lines["de"].append(f"💳 Zahlung IBAN: {masked_iban} (****{last4})")

    return {
        "summary": "\n".join(summary_lines[lang_key]),
        "booking_url": booking_url,
        "seat_reservation_url": seat_url,
        "ticket_recommendation": recommendation,
        "origin": origin,
        "destination": destination,
        "date": date_str,
        "time": travel_time,
        "passengers": passengers,
        "class": travel_class,
        "iban_masked": masked_iban,
        "iban_last4": last4,
    }
