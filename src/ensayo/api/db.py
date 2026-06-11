"""SQLite access + idempotent on-startup migrations (docs/adr/0002, spec §15.1).

``migrate()`` runs on every API start: ``CREATE TABLE IF NOT EXISTS`` plus
``ADD COLUMN`` guarded against "duplicate column". Safe to re-run; no separate
migration tool. New schema changes follow the same add-column pattern.
"""

from __future__ import annotations

import os
import re
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


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _add_column(conn: sqlite3.Connection, table: str, coldef: str) -> None:
    """Add a column if it isn't there yet (the idempotent migration primitive).

    Identifiers can't be bound parameters, so reject anything that isn't a bare
    identifier before it reaches the f-strings below."""
    col = coldef.split()[0]
    if not _IDENT.match(table) or not _IDENT.match(col):
        raise ValueError(f"invalid identifier in migration: {table}.{col}")
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
            last_published_at     TEXT,
            FOREIGN KEY (owner_uc_id) REFERENCES uc_accounts(id)
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id            TEXT PRIMARY KEY,
            simulation_id TEXT NOT NULL,
            employee_slug TEXT NOT NULL,
            student_name  TEXT DEFAULT '',
            student_email TEXT DEFAULT '',
            slot_start    TEXT NOT NULL,
            slot_end      TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'confirmed',
            created_at    TEXT NOT NULL,
            FOREIGN KEY (simulation_id) REFERENCES simulations(id)
        );
        -- The check-then-insert in create_booking() is not atomic; this closes
        -- the double-booking race. Partial so cancelled slots can be rebooked.
        CREATE UNIQUE INDEX IF NOT EXISTS idx_booking_slot
            ON bookings (simulation_id, employee_slug, slot_start)
            WHERE status = 'confirmed';

        CREATE TABLE IF NOT EXISTS visibility_rules (
            id            TEXT PRIMARY KEY,
            simulation_id TEXT NOT NULL,
            unit_code     TEXT DEFAULT '',
            target_type   TEXT NOT NULL,
            target_id     TEXT NOT NULL,
            action        TEXT NOT NULL DEFAULT 'hide',
            trigger_type  TEXT NOT NULL DEFAULT 'always',
            trigger_value TEXT DEFAULT '',
            created_at    TEXT NOT NULL,
            FOREIGN KEY (simulation_id) REFERENCES simulations(id)
        );

        CREATE TABLE IF NOT EXISTS student_access (
            id             TEXT PRIMARY KEY,
            simulation_id  TEXT NOT NULL,
            unit_code      TEXT DEFAULT '',
            auth_mode      TEXT NOT NULL DEFAULT 'individual_account',
            email          TEXT,
            name           TEXT DEFAULT '',
            password_hash  TEXT DEFAULT '',
            status         TEXT NOT NULL DEFAULT 'active',
            progress       TEXT DEFAULT '{}',
            reset_code     TEXT DEFAULT '',
            reset_expires  TEXT DEFAULT '',
            first_access_at TEXT,
            last_access_at  TEXT,
            deleted_at     TEXT,
            created_at     TEXT NOT NULL,
            FOREIGN KEY (simulation_id) REFERENCES simulations(id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_student_email
            ON student_access (simulation_id, email);

        CREATE TABLE IF NOT EXISTS student_whitelist (
            id            TEXT PRIMARY KEY,
            simulation_id TEXT NOT NULL,
            email         TEXT NOT NULL,
            created_at    TEXT NOT NULL,
            FOREIGN KEY (simulation_id) REFERENCES simulations(id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_whitelist_email
            ON student_whitelist (simulation_id, email);

        CREATE TABLE IF NOT EXISTS applications (
            id            TEXT PRIMARY KEY,
            simulation_id TEXT NOT NULL,
            student_id    TEXT NOT NULL,
            company_slug  TEXT DEFAULT '',
            job_title     TEXT DEFAULT '',
            current_stage TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'active',
            cycle         INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL,
            FOREIGN KEY (simulation_id) REFERENCES simulations(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id             TEXT PRIMARY KEY,
            simulation_id  TEXT NOT NULL,
            student_id     TEXT NOT NULL,
            application_id TEXT,
            inbox          TEXT NOT NULL DEFAULT 'work',
            sender_name    TEXT DEFAULT 'System',
            subject        TEXT DEFAULT '',
            body           TEXT DEFAULT '',
            channel        TEXT NOT NULL DEFAULT 'in_app',
            is_read        INTEGER NOT NULL DEFAULT 0,
            deliver_at     TEXT NOT NULL,
            created_at     TEXT NOT NULL,
            FOREIGN KEY (simulation_id) REFERENCES simulations(id)
        );

        CREATE TABLE IF NOT EXISTS conversation_sessions (
            id                TEXT PRIMARY KEY,
            simulation_id     TEXT NOT NULL,
            student_id        TEXT NOT NULL,
            application_id    TEXT,
            kind              TEXT NOT NULL DEFAULT 'conversation',
            persona_slug      TEXT DEFAULT '',
            persona_name      TEXT DEFAULT '',
            system_prompt     TEXT DEFAULT '',
            transcript        TEXT DEFAULT '[]',
            status            TEXT NOT NULL DEFAULT 'active',
            turn_count        INTEGER NOT NULL DEFAULT 0,
            target_turns      INTEGER NOT NULL DEFAULT 4,
            on_complete_event TEXT DEFAULT '',
            assessment_json   TEXT DEFAULT '',
            created_at        TEXT NOT NULL,
            completed_at      TEXT,
            FOREIGN KEY (simulation_id) REFERENCES simulations(id)
        );

        CREATE TABLE IF NOT EXISTS doc_submissions (
            id                TEXT PRIMARY KEY,
            simulation_id     TEXT NOT NULL,
            student_id        TEXT NOT NULL,
            application_id    TEXT,
            title             TEXT DEFAULT '',
            body              TEXT DEFAULT '',
            score             INTEGER,
            feedback          TEXT DEFAULT '',
            focus_areas       TEXT DEFAULT '[]',
            outcome           TEXT DEFAULT '',
            status            TEXT NOT NULL DEFAULT 'submitted',
            on_complete_event TEXT DEFAULT '',
            review_deliver_at TEXT NOT NULL,
            created_at        TEXT NOT NULL,
            reviewed_at       TEXT,
            FOREIGN KEY (simulation_id) REFERENCES simulations(id)
        );

        CREATE TABLE IF NOT EXISTS group_chat_sessions (
            id                 TEXT PRIMARY KEY,
            simulation_id      TEXT NOT NULL,
            student_id         TEXT NOT NULL,
            application_id     TEXT,
            occasion           TEXT DEFAULT '',
            participants_json  TEXT DEFAULT '[]',
            status             TEXT NOT NULL DEFAULT 'active',
            participation_notes TEXT DEFAULT '',
            created_at         TEXT NOT NULL,
            completed_at       TEXT,
            FOREIGN KEY (simulation_id) REFERENCES simulations(id)
        );

        CREATE TABLE IF NOT EXISTS group_chat_posts (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            sequence    INTEGER NOT NULL,
            author_kind TEXT NOT NULL DEFAULT 'character',
            author_name TEXT DEFAULT '',
            content     TEXT DEFAULT '',
            deliver_at  TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES group_chat_sessions(id)
        );
        """
    )
    # Idempotent column additions for existing databases (spec §15.1 pattern).
    _add_column(conn, "simulations", "last_published_at TEXT")
    _add_column(conn, "simulations", "auth_mode TEXT NOT NULL DEFAULT 'shared_password'")
    _add_column(conn, "simulations", "workflow TEXT DEFAULT ''")
    _add_column(conn, "student_access", "reset_attempts INTEGER NOT NULL DEFAULT 0")
    conn.commit()


def init_db() -> sqlite3.Connection:
    conn = connect()
    migrate(conn)
    return conn
