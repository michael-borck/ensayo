"""Student authentication: individual accounts, email-only, and password reset.

Three per-simulation auth modes (spec §6.3): ``shared_password`` (Phase 3),
``individual_account`` (email + password), and ``email_only``. Student sessions
use their own JWT (``typ=student``), distinct from UC sessions. Password reset
emails go via SMTP when configured; otherwise the code is returned so the UC can
relay it (or reset manually).
"""

from __future__ import annotations

import os
import secrets
import smtplib
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import jwt
from fastapi import Header, HTTPException

from .auth import hash_password, jwt_secret, verify_password

_ALGO = "HS256"
_TOKEN_TTL = timedelta(hours=12)
_RESET_TTL = timedelta(hours=1)


class StudentError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- tokens ----------------------------------------------------------------

def create_student_token(student_id: str, slug: str) -> str:
    now = _now()
    return jwt.encode({"sub": student_id, "sim": slug, "typ": "student",
                       "iat": now, "exp": now + _TOKEN_TTL},
                      jwt_secret(), algorithm=_ALGO)


def current_student(authorization: str = Header(default="")) -> dict:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing student token")
    try:
        p = jwt.decode(authorization.split(" ", 1)[1].strip(), jwt_secret(),
                       algorithms=[_ALGO])
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "invalid or expired token") from exc
    if p.get("typ") != "student":
        raise HTTPException(401, "not a student token")
    return {"id": p["sub"], "slug": p["sim"]}


# --- helpers ---------------------------------------------------------------

def _public(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "email": row["email"], "name": row["name"],
            "status": row["status"]}


def get_student(conn: sqlite3.Connection, sim_id: str, email: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM student_access WHERE simulation_id = ? AND email = ?",
        (sim_id, email.lower())).fetchone()


def _whitelisted(conn: sqlite3.Connection, sim_id: str, email: str) -> bool:
    """True if email is allowed: open registration unless a whitelist exists."""
    has_list = conn.execute(
        "SELECT 1 FROM student_whitelist WHERE simulation_id = ? LIMIT 1",
        (sim_id,)).fetchone()
    if not has_list:
        return True
    return bool(conn.execute(
        "SELECT 1 FROM student_whitelist WHERE simulation_id = ? AND email = ?",
        (sim_id, email.lower())).fetchone())


def _touch_access(conn: sqlite3.Connection, student_id: str) -> None:
    now = _now().isoformat()
    conn.execute(
        "UPDATE student_access SET last_access_at = ?, "
        "first_access_at = COALESCE(first_access_at, ?) WHERE id = ?",
        (now, now, student_id))
    conn.commit()


# --- operations ------------------------------------------------------------

def register(conn: sqlite3.Connection, sim: sqlite3.Row, email: str, name: str,
             password: str) -> dict:
    if sim["auth_mode"] != "individual_account":
        raise StudentError("this simulation does not use individual accounts")
    email = email.strip().lower()
    if not email or not password:
        raise StudentError("email and password are required")
    if not _whitelisted(conn, sim["id"], email):
        raise StudentError("this email is not on the class list", status=403)
    existing = get_student(conn, sim["id"], email)
    if existing and existing["deleted_at"] is None:
        raise StudentError("an account already exists for this email", status=409)
    sid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO student_access (id, simulation_id, auth_mode, email, name, "
        "password_hash, status, created_at) VALUES (?,?,?,?,?,?,'active',?)",
        (sid, sim["id"], "individual_account", email, name,
         hash_password(password), _now().isoformat()))
    conn.commit()
    return _public(conn.execute("SELECT * FROM student_access WHERE id = ?", (sid,)).fetchone())


def login(conn: sqlite3.Connection, sim: sqlite3.Row, email: str,
          password: str = "") -> tuple[dict, str]:
    email = email.strip().lower()
    mode = sim["auth_mode"]

    if mode == "individual_account":
        s = get_student(conn, sim["id"], email)
        if s is None or s["deleted_at"] is not None or not verify_password(password, s["password_hash"]):
            raise StudentError("invalid email or password", status=401)

    elif mode == "email_only":
        if not email:
            raise StudentError("email is required", status=400)
        if not _whitelisted(conn, sim["id"], email):
            raise StudentError("this email is not on the class list", status=403)
        s = get_student(conn, sim["id"], email)
        if s is None:
            sid = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO student_access (id, simulation_id, auth_mode, email, "
                "status, created_at) VALUES (?,?, 'email_only', ?, 'active', ?)",
                (sid, sim["id"], email, _now().isoformat()))
            conn.commit()
            s = conn.execute("SELECT * FROM student_access WHERE id = ?", (sid,)).fetchone()
        elif s["deleted_at"] is not None:
            raise StudentError("this account has been removed", status=403)
    else:
        raise StudentError("this simulation uses a shared password", status=400)

    _touch_access(conn, s["id"])
    return _public(s), create_student_token(s["id"], sim["slug"])


def request_reset(conn: sqlite3.Connection, sim: sqlite3.Row, email: str) -> dict:
    s = get_student(conn, sim["id"], email.strip().lower())
    # Don't reveal whether the email exists.
    if s is None or s["deleted_at"] is not None or sim["auth_mode"] != "individual_account":
        return {"sent": False, "message": "If that account exists, a reset code was issued."}
    code = f"{secrets.randbelow(1_000_000):06d}"
    conn.execute("UPDATE student_access SET reset_code = ?, reset_expires = ? WHERE id = ?",
                 (code, (_now() + _RESET_TTL).isoformat(), s["id"]))
    conn.commit()
    sent = send_email(s["email"], f"Password reset — {sim['name']}",
                      f"Your password reset code is: {code}\nIt expires in 1 hour.")
    result = {"sent": sent, "message": "Reset code issued."}
    if not sent:
        result["code"] = code  # SMTP not configured: surface so the UC can relay it
    return result


def reset(conn: sqlite3.Connection, sim: sqlite3.Row, email: str, code: str,
          new_password: str) -> dict:
    s = get_student(conn, sim["id"], email.strip().lower())
    if s is None or not s["reset_code"] or s["reset_code"] != code:
        raise StudentError("invalid reset code", status=400)
    if not s["reset_expires"] or _now() > datetime.fromisoformat(s["reset_expires"]):
        raise StudentError("reset code has expired", status=400)
    if not new_password:
        raise StudentError("new password is required")
    conn.execute("UPDATE student_access SET password_hash = ?, reset_code = '', "
                 "reset_expires = '' WHERE id = ?",
                 (hash_password(new_password), s["id"]))
    conn.commit()
    return {"reset": True}


# --- SMTP ------------------------------------------------------------------

def send_email(to: str, subject: str, body: str) -> bool:
    """Send via SMTP if configured (SMTP_HOST/PORT/USER/PASSWORD/FROM). Else False."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        return False
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "ensayo@localhost"))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls()
            user, pw = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD")
            if user and pw:
                smtp.login(user, pw)
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError):
        return False
