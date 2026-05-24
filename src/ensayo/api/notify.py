"""Notification adapter (spec §3.7).

All student communications go through one ``notify()`` dispatcher rather than
straight to a channel, so new channels (email, Telegram, …) plug in via
``register_channel`` without touching call sites. MVP ships the in-app inbox only;
it persists a message row with a ``deliver_at`` for lazy delivery (ADR-0007).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Callable

ChannelHandler = Callable[..., None]
_CHANNELS: dict[str, ChannelHandler] = {}


def register_channel(name: str, handler: ChannelHandler) -> None:
    _CHANNELS[name] = handler


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _in_app(conn: sqlite3.Connection, *, student_id: str, simulation_id: str,
            subject: str, body: str, sender_name: str, inbox: str,
            application_id: str | None, deliver_at: str | None) -> None:
    conn.execute(
        "INSERT INTO messages (id, simulation_id, student_id, application_id, inbox, "
        "sender_name, subject, body, channel, deliver_at, created_at) "
        "VALUES (?,?,?,?,?,?,?,?, 'in_app', ?, ?)",
        (str(uuid.uuid4()), simulation_id, student_id, application_id, inbox,
         sender_name, subject, body, deliver_at or _now(), _now()))
    conn.commit()


register_channel("in_app", _in_app)


def notify(conn: sqlite3.Connection, *, student_id: str, simulation_id: str,
           subject: str = "", body: str = "", sender_name: str = "System",
           inbox: str = "work", application_id: str | None = None,
           deliver_at: str | None = None, channels: list[str] | None = None) -> None:
    """Dispatch a notification to the given channels (default: in-app inbox)."""
    for name in (channels or ["in_app"]):
        handler = _CHANNELS.get(name)
        if handler:
            handler(conn, student_id=student_id, simulation_id=simulation_id,
                    subject=subject, body=body, sender_name=sender_name, inbox=inbox,
                    application_id=application_id, deliver_at=deliver_at)
