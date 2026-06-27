"""UC authentication: bcrypt password hashing + JWT sessions (spec §6, §10.1)."""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, Request

from .db import connect

_ALGO = "HS256"
_TOKEN_TTL = timedelta(hours=24)


def jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        # Dev fallback — fine for local/zero-config, must be set in production.
        secret = "ensayo-dev-secret-change-me"
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, TypeError):
        return False


def create_token(uc_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": uc_id, "iat": now, "exp": now + _TOKEN_TTL}
    return jwt.encode(payload, jwt_secret(), algorithm=_ALGO)


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=[_ALGO])
        return payload["sub"]
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid or expired token") from exc


# --- account helpers -------------------------------------------------------

def create_uc(conn: sqlite3.Connection, email: str, password: str,
              display_name: str = "", role: str = "uc",
              verified: bool = True) -> dict:
    """Create a UC account. CLI/admin-created accounts are verified by default;
    self-registered accounts pass ``verified=False`` pending email confirmation."""
    if get_uc_by_email(conn, email):
        raise ValueError(f"a UC account already exists for {email}")
    uc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO uc_accounts "
        "(id, email, password_hash, display_name, role, is_verified, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uc_id, email.lower(), hash_password(password), display_name or email, role,
         1 if verified else 0, now),
    )
    conn.commit()
    return {"id": uc_id, "email": email.lower(), "display_name": display_name or email,
            "role": role, "is_verified": 1 if verified else 0}


def get_uc_by_email(conn: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM uc_accounts WHERE email = ?", (email.lower(),)).fetchone()


def get_uc_by_id(conn: sqlite3.Connection, uc_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM uc_accounts WHERE id = ?", (uc_id,)).fetchone()


# --- FastAPI dependency ----------------------------------------------------

def get_conn(request: Request) -> sqlite3.Connection:
    conn = getattr(request.app.state, "conn", None)
    if conn is None:
        conn = connect()
        request.app.state.conn = conn
    return conn


def current_uc(
    authorization: str = Header(default=""),
    conn: sqlite3.Connection = Depends(get_conn),
) -> sqlite3.Row:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    uc_id = decode_token(authorization.split(" ", 1)[1].strip())
    uc = get_uc_by_id(conn, uc_id)
    if uc is None:
        raise HTTPException(status_code=401, detail="account not found")
    return uc
