"""UC self-registration with email-code verification.

Mirrors the AI Exchange pattern (domain allowlist + 6-digit code emailed on
register, verified on confirm), adapted to Ensayo's SQLite/auth helpers.

Codes are stored plaintext in ``uc_verifications`` so they can be surfaced in
the admin panel when no SMTP provider is configured (the demo-safe fallback —
the admin relays the code out-of-band). Codes are 8-char upper-alphanumeric,
single-use, and expire after 1 hour.

Account lockout is email-keyed (5 fails / 15 min); per-IP spray is handled by
the rate limiter in :mod:`ratelimit`. Self-registered accounts are always role
``uc`` — instance admins are bootstrapped via the CLI.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
import string
import uuid
from datetime import datetime, timedelta, timezone

from .auth import create_token, create_uc, get_uc_by_email
from .studentauth import send_email

_CODE_TTL = timedelta(minutes=60)
_CODE_CHARSET = string.ascii_uppercase + string.digits  # no ambiguous? keep simple
_CODE_LEN = 8
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW = timedelta(minutes=15)


class RegistrationError(Exception):
    """Raised with a user-facing message + HTTP-ish status."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- domain allowlist ------------------------------------------------------

def allowed_domains() -> list[str]:
    """Allowed email domains from ``ALLOWED_DOMAINS`` (comma-sep). Empty = open.

    Open-by-default keeps local/dev frictionless; set the env on a public
    instance to restrict sign-ups."""
    raw = os.environ.get("ALLOWED_DOMAINS", "").strip()
    return [d.strip().lower().lstrip("@") for d in raw.split(",") if d.strip()]


def domain_allowed(email: str) -> bool:
    domains = allowed_domains()
    if not domains:
        return True  # not configured → open (document for operators)
    try:
        return email.strip().lower().split("@", 1)[1] in domains
    except IndexError:
        return False


# --- instance settings (registration freeze) -------------------------------

def registration_open(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT value FROM instance_settings WHERE key = 'registration_open'"
    ).fetchone()
    # Default open if the row is somehow missing.
    return (row is None) or (row["value"] == "1")


def set_registration_open(conn: sqlite3.Connection, open_: bool) -> bool:
    conn.execute(
        "INSERT INTO instance_settings (key, value) VALUES ('registration_open', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("1" if open_ else "0",))
    conn.commit()
    return open_


# --- verification codes ----------------------------------------------------

def _new_code() -> str:
    return "".join(secrets.choice(_CODE_CHARSET) for _ in range(_CODE_LEN))


def _issue_code(conn: sqlite3.Connection, uc_id: str) -> str:
    """Create a fresh verification code row for *uc_id* and return the code.

    Old codes are left in place (marked used) so only the newest is valid."""
    conn.execute("UPDATE uc_verifications SET used = 1 WHERE uc_id = ?", (uc_id,))
    code = _new_code()
    conn.execute(
        "INSERT INTO uc_verifications (id, uc_id, code, expires_at, used, created_at) "
        "VALUES (?, ?, ?, ?, 0, ?)",
        (str(uuid.uuid4()), uc_id, code,
         (_now() + _CODE_TTL).isoformat(), _now().isoformat()))
    conn.commit()
    return code


def _send_code(email: str, code: str) -> bool:
    body = (
        "Your Ensayo verification code is:\n\n"
        f"    {code}\n\n"
        "It expires in 1 hour. If you didn't request this, ignore this email.")
    return send_email(email, "Your Ensayo verification code", body)


# --- operations ------------------------------------------------------------

def register(conn: sqlite3.Connection, email: str, password: str,
             display_name: str = "") -> dict:
    """Self-register an unverified UC and email a code.

    Returns ``{email, verification_sent}``. When SMTP isn't configured the code
    is still stored (``verification_sent=False``) and the admin can relay it via
    :func:`pending_codes`."""
    email = email.strip().lower()
    if not registration_open(conn):
        raise RegistrationError("Registration is currently closed.", 403)
    if not domain_allowed(email):
        raise RegistrationError(
            "Sign-ups from this email domain are not allowed.", 403)
    if get_uc_by_email(conn, email):
        # Don't leak existence — but a re-register of an unverified account
        # should let them get a fresh code rather than hard-error.
        raise RegistrationError(
            "An account with this email already exists. Use resend-code or sign in.", 409)
    if len(password) < 8:
        raise RegistrationError("Password must be at least 8 characters.", 422)

    uc = create_uc(conn, email, password, display_name=display_name,
                   role="uc", verified=False)
    code = _issue_code(conn, uc["id"])
    sent = _send_code(email, code)
    return {"email": email, "verification_sent": sent}


def resend_code(conn: sqlite3.Connection, email: str) -> dict:
    email = email.strip().lower()
    uc = get_uc_by_email(conn, email)
    if uc is None:
        # Don't enumerate — return success-shaped response.
        return {"email": email, "verification_sent": False}
    if uc["is_verified"]:
        return {"email": email, "verification_sent": False, "already_verified": True}
    code = _issue_code(conn, uc["id"])
    sent = _send_code(email, code)
    return {"email": email, "verification_sent": sent}


def verify_email(conn: sqlite3.Connection, email: str, code: str) -> dict:
    """Confirm the code, mark the UC verified, and issue a session token."""
    email = email.strip().lower()
    uc = get_uc_by_email(conn, email)
    if uc is None:
        raise RegistrationError("No account found for this email.", 404)
    row = conn.execute(
        "SELECT * FROM uc_verifications WHERE uc_id = ? AND code = ? AND used = 0 "
        "ORDER BY created_at DESC LIMIT 1",
        (uc["id"], code.strip().upper())).fetchone()
    if row is None:
        raise RegistrationError("Invalid verification code.", 400)
    if datetime.fromisoformat(row["expires_at"]) < _now():
        raise RegistrationError("Verification code has expired. Request a new one.", 410)
    conn.execute("UPDATE uc_verifications SET used = 1 WHERE id = ?", (row["id"],))
    conn.execute("UPDATE uc_accounts SET is_verified = 1 WHERE id = ?", (uc["id"],))
    conn.commit()
    return {
        "verified": True,
        "token": create_token(uc["id"]),
        "uc": {"id": uc["id"], "email": uc["email"],
               "display_name": uc["display_name"], "role": uc["role"]},
    }


# --- account lockout -------------------------------------------------------

def record_login_attempt(conn: sqlite3.Connection, email: str, success: bool,
                         ip: str | None = None) -> None:
    conn.execute(
        "INSERT INTO uc_login_attempts (id, email, ip, success, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), email.strip().lower(), ip or "",
         1 if success else 0, _now().isoformat()))
    conn.commit()


def is_locked_out(conn: sqlite3.Connection, email: str) -> bool:
    since = (_now() - LOCKOUT_WINDOW).isoformat()
    fails = conn.execute(
        "SELECT COUNT(*) AS n FROM uc_login_attempts "
        "WHERE email = ? AND success = 0 AND created_at > ?",
        (email.strip().lower(), since)).fetchone()["n"]
    return fails >= MAX_FAILED_ATTEMPTS


# --- admin views -----------------------------------------------------------

def pending_codes(conn: sqlite3.Connection) -> list[dict]:
    """Unverified UCs + their newest valid code, for admin relay when no SMTP.

    Only exposed to instance admins. The code is included verbatim because the
    whole point of the fallback is to surface it."""
    rows = conn.execute(
        "SELECT u.email, u.display_name, u.created_at, v.code, v.expires_at "
        "FROM uc_accounts u LEFT JOIN uc_verifications v ON v.uc_id = u.id "
        "WHERE u.is_verified = 0 AND v.used = 0 "
        "AND v.id = (SELECT MAX(id) FROM uc_verifications v2 "
        "            WHERE v2.uc_id = u.id AND v2.used = 0) "
        "ORDER BY u.created_at DESC").fetchall()
    return [{"email": r["email"], "display_name": r["display_name"],
             "code": r["code"], "expires_at": r["expires_at"]}
            for r in rows]


def list_users(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, email, display_name, role, is_verified, created_at, "
        "last_login_at FROM uc_accounts ORDER BY created_at DESC").fetchall()
    return [{"id": r["id"], "email": r["email"], "display_name": r["display_name"],
             "role": r["role"], "is_verified": bool(r["is_verified"]),
             "created_at": r["created_at"], "last_login_at": r["last_login_at"]}
            for r in rows]
