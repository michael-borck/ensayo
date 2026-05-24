"""SQLite access + idempotent on-startup migrations (docs/adr/0002, spec §15.1).

``migrate()`` runs on every API start: ``CREATE TABLE IF NOT EXISTS`` plus
``ADD COLUMN`` guarded against "duplicate column". Safe to re-run; no separate
migration tool. New schema changes follow the same add-column pattern.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def db_path() -> Path:
    """Resolve the SQLite file path (env ``ENSAYO_DB``, default repo-local)."""
    raw = os.environ.get("ENSAYO_DB", "./.ensayo-data/ensayo.db")
    return Path(raw).expanduser()


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _add_column(conn: sqlite3.Connection, table: str, coldef: str) -> None:
    """Add a column if it isn't there yet (the idempotent migration primitive)."""
    col = coldef.split()[0]
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    if col not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS uc_accounts (
            id            TEXT PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name  TEXT DEFAULT '',
            role          TEXT NOT NULL DEFAULT 'uc',
            created_at    TEXT NOT NULL,
            last_login_at TEXT
        );

        CREATE TABLE IF NOT EXISTS simulations (
            id                    TEXT PRIMARY KEY,
            name                  TEXT NOT NULL,
            slug                  TEXT UNIQUE NOT NULL,
            type                  TEXT NOT NULL DEFAULT 'single_company',
            audience              TEXT NOT NULL DEFAULT 'adults',
            owner_uc_id           TEXT NOT NULL,
            repo_url              TEXT DEFAULT '',
            working_clone_path    TEXT DEFAULT '',
            site_url              TEXT DEFAULT '',
            status                TEXT NOT NULL DEFAULT 'draft',
            has_unpublished_changes INTEGER NOT NULL DEFAULT 0,
            auto_publish          INTEGER NOT NULL DEFAULT 0,
            shared_password_hash  TEXT DEFAULT '',
            config_cache          TEXT DEFAULT '{}',
            created_at            TEXT NOT NULL,
            updated_at            TEXT NOT NULL,
            FOREIGN KEY (owner_uc_id) REFERENCES uc_accounts(id)
        );
        """
    )
    # Future column additions go here via _add_column(conn, "table", "col TYPE ...").
    conn.commit()


def init_db() -> sqlite3.Connection:
    conn = connect()
    migrate(conn)
    return conn
