"""Group chat surface (spec §12, generalised from WorkReady's lunchroom).

A multi-participant chat: a student plus several AI co-workers. Pre-planned
character "beats" are delivered lazily on a stagger (ADR-0007); the student posts
between them; completion produces a participation review. (Beat-arc @mention
rescheduling is a later refinement; beats here are provided at start.)
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone


class GroupChatError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _participants(raw: list) -> list[dict]:
    out = []
    for p in raw or []:
        if isinstance(p, dict):
            out.append({"name": p.get("name") or p.get("slug") or "Colleague"})
        else:
            out.append({"name": str(p)})
    return out or [{"name": "Colleague"}]


def _add_post(conn: sqlite3.Connection, session_id: str, seq: int, *, author_kind: str,
              author_name: str, content: str, deliver_at: str) -> None:
    conn.execute(
        "INSERT INTO group_chat_posts (id, session_id, sequence, author_kind, "
        "author_name, content, deliver_at, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), session_id, seq, author_kind, author_name, content,
         deliver_at, _now().isoformat()))


def start(conn: sqlite3.Connection, sim: sqlite3.Row, student_id: str, *, occasion: str,
          participants: list | None = None, beats: list | None = None,
          application_id: str | None = None, beat_interval_seconds: int = 0) -> dict:
    people = _participants(participants)
    gid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO group_chat_sessions (id, simulation_id, student_id, application_id, "
        "occasion, participants_json, status, created_at) VALUES (?,?,?,?,?,?, 'active', ?)",
        (gid, sim["id"], student_id, application_id, occasion,
         json.dumps(people), _now().isoformat()))

    now = _now()
    _add_post(conn, gid, 0, author_kind="system", author_name="",
              content=f"— {occasion} —", deliver_at=now.isoformat())
    for i, beat in enumerate(beats or [], start=1):
        if isinstance(beat, dict):
            author = beat.get("author") or people[(i - 1) % len(people)]["name"]
            content = beat.get("content", "")
        else:
            author = people[(i - 1) % len(people)]["name"]
            content = str(beat)
        deliver_at = (now + timedelta(seconds=beat_interval_seconds * i)).isoformat()
        _add_post(conn, gid, i, author_kind="character", author_name=author,
                  content=content, deliver_at=deliver_at)
    conn.commit()
    return get(conn, sim, gid, student_id)


def post(conn: sqlite3.Connection, sim: sqlite3.Row, gid: str, student_id: str,
         text: str) -> dict:
    sess = _session_row(conn, sim, gid, student_id)
    if sess["status"] != "active":
        raise GroupChatError("group chat already completed")
    if not text.strip():
        raise GroupChatError("message is empty")
    seq = (conn.execute("SELECT COALESCE(MAX(sequence), 0) m FROM group_chat_posts "
                        "WHERE session_id = ?", (gid,)).fetchone()["m"]) + 1
    _add_post(conn, gid, seq, author_kind="student", author_name="You",
              content=text, deliver_at=_now().isoformat())
    conn.commit()
    return {"posted": True, "sequence": seq}


def get(conn: sqlite3.Connection, sim: sqlite3.Row, gid: str, student_id: str) -> dict:
    sess = _session_row(conn, sim, gid, student_id)
    now = _now().isoformat()
    posts = conn.execute(
        "SELECT * FROM group_chat_posts WHERE session_id = ? AND deliver_at <= ? "
        "ORDER BY sequence", (gid, now)).fetchall()
    return {
        "id": gid, "occasion": sess["occasion"], "status": sess["status"],
        "participants": json.loads(sess["participants_json"] or "[]"),
        "participation_notes": sess["participation_notes"],
        "posts": [{"sequence": p["sequence"], "author_kind": p["author_kind"],
                   "author_name": p["author_name"], "content": p["content"]} for p in posts],
    }


def complete(conn: sqlite3.Connection, sim: sqlite3.Row, gid: str, student_id: str) -> dict:
    sess = _session_row(conn, sim, gid, student_id)
    n = conn.execute("SELECT COUNT(*) c FROM group_chat_posts WHERE session_id = ? "
                     "AND author_kind = 'student'", (gid,)).fetchone()["c"]
    notes = (f"Student contributed {n} message(s)." +
             (" Good engagement." if n >= 2 else " Limited participation."))
    conn.execute("UPDATE group_chat_sessions SET status = 'completed', "
                 "participation_notes = ?, completed_at = ? WHERE id = ?",
                 (notes, _now().isoformat(), gid))
    conn.commit()
    return {"completed": True, "participation_notes": notes, "student_posts": n}


def _session_row(conn: sqlite3.Connection, sim: sqlite3.Row, gid: str,
                 student_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM group_chat_sessions WHERE id = ? AND simulation_id = ?",
                       (gid, sim["id"])).fetchone()
    if row is None:
        raise GroupChatError("group chat not found", status=404)
    if row["student_id"] != student_id:
        raise GroupChatError("not your group chat", status=403)
    return row
