"""
PII masking tool.

Rules:
- Never return full IBAN/account numbers to UI, logs, traces, or evaluation data.
- Show only the last 4 characters.
"""

from __future__ import annotations

import re


IBAN_REGEX = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b", re.IGNORECASE)


def normalize_account_number(account_number: str | None) -> str:
    if not account_number:
        return ""
    return re.sub(r"\s+", "", account_number.strip())


def mask_account_number(account_number: str | None) -> str | None:
    cleaned = normalize_account_number(account_number)
    if not cleaned:
        return None
    return "*" * max(len(cleaned) - 4, 0) + cleaned[-4:]


def mask_pii_text(text: str | None) -> str:
    if not text:
        return ""

    def _mask(match: re.Match) -> str:
        return mask_account_number(match.group(0)) or "****"

    compact = text
    return IBAN_REGEX.sub(_mask, compact)


def contains_iban_like_text(text: str | None) -> bool:
    if not text:
        return False
    return bool(IBAN_REGEX.search(text.replace(" ", "")))
