"""
Compensation tool.

MVP compensation logic:
- Delay under 60 min: no compensation
- 60 to 119 min: 25%
- 120+ min: 50%

Production replacement:
- official passenger-rights rules
- ticket validation
- claim status system
- payment/voucher workflow
"""

from __future__ import annotations

from app.tools.pii_masking_tool import mask_account_number


def calculate_compensation(delay_minutes: int, ticket_price: float) -> dict:
    if delay_minutes < 60:
        percentage = 0
        reason = "Delay is under 60 minutes."
    elif delay_minutes < 120:
        percentage = 25
        reason = "Delay is between 60 and 119 minutes."
    else:
        percentage = 50
        reason = "Delay is 120 minutes or more."

    amount = round(ticket_price * percentage / 100, 2)

    return {
        "eligible": percentage > 0,
        "percentage": percentage,
        "amount": amount,
        "currency": "EUR",
        "reason": reason,
    }


def submit_compensation_claim(payload: dict) -> dict:
    train_number = str(payload.get("train_number", "")).strip()
    planned_start_time = str(payload.get("planned_start_time", "")).strip()
    actual_start_time = payload.get("actual_start_time")
    trip_not_started = bool(payload.get("trip_not_started", False))
    alternative_transport = str(payload.get("alternative_transport", "none")).strip() or "none"
    refund_method = str(payload.get("refund_method", "")).strip()
    account_number = payload.get("account_number")
    home_address = payload.get("home_address")

    try:
        ticket_price = float(payload.get("ticket_price", 0))
        delay_minutes = int(payload.get("delay_minutes", 0))
    except (TypeError, ValueError):
        raise ValueError("ticket_price must be a number and delay_minutes must be an integer.")

    if not train_number:
        raise ValueError("train_number is required.")
    if not planned_start_time:
        raise ValueError("planned_start_time is required.")
    if ticket_price < 0 or delay_minutes < 0:
        raise ValueError("ticket_price and delay_minutes cannot be negative.")
    if refund_method not in {"bank_account", "voucher"}:
        raise ValueError("refund_method must be 'bank_account' or 'voucher'.")
    if refund_method == "bank_account" and not account_number:
        raise ValueError("account_number is required for bank account refund.")
    if refund_method == "voucher" and not home_address:
        raise ValueError("home_address is required for voucher refund.")

    compensation = calculate_compensation(delay_minutes, ticket_price)

    return {
        "claim_status": "submitted",
        "claim_id": "DEBIAN-CLAIM-MVP-0001",
        "train_number": train_number,
        "planned_start_time": planned_start_time,
        "actual_start_time": actual_start_time,
        "trip_not_started": trip_not_started,
        "alternative_transport": alternative_transport,
        "refund_method": refund_method,
        "masked_account_number": mask_account_number(account_number) if refund_method == "bank_account" else None,
        "home_address_confirmed": bool(home_address) if refund_method == "voucher" else False,
        "compensation": compensation,
    }
