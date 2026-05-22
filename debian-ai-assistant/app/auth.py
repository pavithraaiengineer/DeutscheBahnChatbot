"""
DeBian Role-Based Access Control
=================================
Roles:
  customer   – can check train info, file claims, manage own IBAN
  employee   – can check train info + occupancy status
  admin      – employee + analytics dashboard + full occupancy data

Token: base64(json_payload).base64(hmac_sha256_signature)
No external dependency — stdlib only.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from pathlib import Path

from app.tools.pii_masking_tool import mask_account_number

_SECRET = os.environ.get("AUTH_SECRET", "debian-local-secret-change-in-prod")
_USER_DB_PATH = Path("runtime_logs/users.json")

ROLES = {"customer", "employee", "admin"}
ROLE_HIERARCHY = {"admin": 3, "employee": 2, "customer": 1}

# ---------------------------------------------------------------------------
# User store (file-backed JSON for local; swap for BigQuery/Firestore in prod)
# ---------------------------------------------------------------------------

def _load_users() -> dict:
    if not _USER_DB_PATH.exists():
        _USER_DB_PATH.parent.mkdir(exist_ok=True)
        # Seed demo users
        demo = {
            "customer_demo": {
                "user_id": "customer_demo",
                "username": "customer_demo",
                "password_hash": _hash_password("customer123"),
                "role": "customer",
                "full_name": "Maria Müller",
                "email": "maria@example.com",
                "iban": "DE89370400440532013000",
                "created_at": "2026-01-01T00:00:00Z",
            },
            "employee_demo": {
                "user_id": "employee_demo",
                "username": "employee_demo",
                "password_hash": _hash_password("employee123"),
                "role": "employee",
                "full_name": "Hans Schmidt",
                "email": "hans@bahn.de",
                "iban": None,
                "created_at": "2026-01-01T00:00:00Z",
            },
            "admin_demo": {
                "user_id": "admin_demo",
                "username": "admin_demo",
                "password_hash": _hash_password("admin123"),
                "role": "admin",
                "full_name": "Klaus Weber",
                "email": "admin@bahn.de",
                "iban": None,
                "created_at": "2026-01-01T00:00:00Z",
            },
        }
        _USER_DB_PATH.write_text(json.dumps(demo, indent=2), encoding="utf-8")
        return demo
    return json.loads(_USER_DB_PATH.read_text(encoding="utf-8"))


def _save_users(users: dict) -> None:
    _USER_DB_PATH.parent.mkdir(exist_ok=True)
    _USER_DB_PATH.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _hash_password(password: str) -> str:
    return hashlib.sha256(f"{_SECRET}:{password}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def _sign(payload: dict) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{sig}"


def _verify(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        encoded, sig = parts
        expected = hmac.new(_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(encoded + "==").decode())
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def issue_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400 * 7,  # 7 days
        "jti": str(uuid.uuid4())[:8],
    }
    return _sign(payload)


def decode_token(token: str) -> dict | None:
    return _verify(token)


# ---------------------------------------------------------------------------
# Auth actions
# ---------------------------------------------------------------------------

def login(username: str, password: str) -> dict:
    users = _load_users()
    user = users.get(username)
    if not user or user["password_hash"] != _hash_password(password):
        return {"success": False, "error": "Invalid username or password."}

    token = issue_token(user["user_id"], user["role"])
    safe = _safe_user(user)
    return {"success": True, "token": token, "user": safe}


def register(username: str, password: str, full_name: str,
             email: str, role: str = "customer") -> dict:
    if role not in ROLES:
        return {"success": False, "error": f"Invalid role. Choose: {', '.join(ROLES)}"}
    users = _load_users()
    if username in users:
        return {"success": False, "error": "Username already exists."}

    user_id = username
    users[user_id] = {
        "user_id": user_id,
        "username": username,
        "password_hash": _hash_password(password),
        "role": role,
        "full_name": full_name,
        "email": email,
        "iban": None,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _save_users(users)
    token = issue_token(user_id, role)
    return {"success": True, "token": token, "user": _safe_user(users[user_id])}


def update_iban(user_id: str, iban: str) -> dict:
    users = _load_users()
    if user_id not in users:
        return {"success": False, "error": "User not found."}
    # Validate IBAN: at least 15 chars, alphanumeric
    iban_clean = iban.replace(" ", "").upper()
    if len(iban_clean) < 15:
        return {"success": False, "error": "IBAN too short."}
    users[user_id]["iban"] = iban_clean
    _save_users(users)
    return {"success": True, "masked_iban": mask_account_number(iban_clean)}


def get_profile(user_id: str) -> dict | None:
    users = _load_users()
    user = users.get(user_id)
    return _safe_user(user) if user else None


def require_role(token: str, min_role: str) -> tuple[dict | None, str | None]:
    """Returns (token_payload, error). error is None on success."""
    payload = decode_token(token)
    if not payload:
        return None, "Invalid or expired token. Please log in again."
    role = payload.get("role", "customer")
    if ROLE_HIERARCHY.get(role, 0) < ROLE_HIERARCHY.get(min_role, 0):
        return None, f"Access denied. Required role: {min_role}, your role: {role}."
    return payload, None


def _safe_user(user: dict) -> dict:
    """Return user dict with IBAN masked and password removed."""
    out = {k: v for k, v in user.items() if k not in {"password_hash"}}
    if user.get("iban"):
        out["masked_iban"] = mask_account_number(user["iban"])
        out["iban"] = "***HIDDEN***"
    return out
