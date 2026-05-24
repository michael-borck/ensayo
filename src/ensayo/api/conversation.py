"""1-on-1 conversation surface (spec §12).

A multi-turn conversation between a student and one virtual employee, parameterised
by ``kind`` (hiring_interview, coaching, exit_interview, consultation, …). On
completion it runs an assessment and, if wired to an application via
``on_complete_event``, emits that event so the workflow advances itself — closing
the surface → event → workflow loop. Stub-backed so it runs offline.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..assess import assess
from ..llm import get_provider
from . import workflow_runtime as wfr
from .notify import notify


class ConversationError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_KIND_WRAPPER = {
    "hiring_interview": "You are interviewing this student for a role. Ask focused "
                        "questions one at a time and probe their answers.",
    "coaching": "You are a mid-placement coach. Help the student reflect and improve.",
    "exit_interview": "You are conducting an exit interview. Ask what they learned.",
    "consultation": "You are consulting with the student on the case. Ask clarifying "
                    "questions and guide them.",
}


def _persona_prompt(sim: sqlite3.Row, persona_slug: str) -> str:
    root = Path(sim["working_clone_path"])
    direct = root / "content" / "employees" / f"{persona_slug}-prompt.txt"
    if direct.exists():
        return direct.read_text(encoding="utf-8")
    for p in root.glob(f"companies/*/content/employees/{persona_slug}-prompt.txt"):
        return p.read_text(encoding="utf-8")
    return f"You are {persona_slug}, an employee. Stay in character and be helpful."


def _stub_reply(kind: str, turn: int) -> str:
    lines = [
        "Thanks for joining. To start — tell me a bit about yourself and why you're here.",
        "Good. Can you give me a specific example?",
        "Interesting. What would you do differently next time?",
        "That's helpful. Anything you'd like to ask me before we wrap up?",
        "Great — thanks for your time today.",
    ]
    return lines[min(turn, len(lines) - 1)]


def _session(conn: sqlite3.Connection, sid: str) -> dict:
    row = conn.execute("SELECT * FROM conversation_sessions WHERE id = ?", (sid,)).fetchone()
    if row is None:
        raise ConversationError("conversation not found", status=404)
    d = dict(row)
    d["transcript"] = json.loads(d["transcript"] or "[]")
    if d["assessment_json"]:
        d["assessment"] = json.loads(d["assessment_json"])
    return d


def start(conn: sqlite3.Connection, sim: sqlite3.Row, student_id: str, *,
          kind: str, persona_slug: str, persona_name: str = "",
          application_id: str | None = None, on_complete_event: str = "",
          target_turns: int = 4) -> dict:
    system = _persona_prompt(sim, persona_slug)
    wrapper = _KIND_WRAPPER.get(kind)
    if wrapper:
        system = f"{system}\n\nFOR THIS CONVERSATION: {wrapper}"

    provider, spec = get_provider(None)
    opening = (_stub_reply(kind, 0) if spec.provider == "stub"
               else provider.generate("Greet the student and ask your first question.",
                                       system=system, max_tokens=200).text)
    transcript = [{"role": "assistant", "content": opening, "ts": _now()}]

    sid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO conversation_sessions (id, simulation_id, student_id, application_id, "
        "kind, persona_slug, persona_name, system_prompt, transcript, status, turn_count, "
        "target_turns, on_complete_event, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?, 'active', 0, ?, ?, ?)",
        (sid, sim["id"], student_id, application_id, kind, persona_slug,
         persona_name or persona_slug, system, json.dumps(transcript),
         target_turns, on_complete_event, _now()))
    conn.commit()
    return _session(conn, sid)


def send_message(conn: sqlite3.Connection, sim: sqlite3.Row, sid: str, student_id: str,
                 text: str) -> dict:
    sess = _session(conn, sid)
    if sess["student_id"] != student_id:
        raise ConversationError("not your conversation", status=403)
    if sess["status"] != "active":
        raise ConversationError("conversation already completed")
    if not text.strip():
        raise ConversationError("message is empty")

    transcript = sess["transcript"]
    transcript.append({"role": "user", "content": text, "ts": _now()})
    turn = sess["turn_count"] + 1

    provider, spec = get_provider(None)
    if spec.provider == "stub":
        reply = _stub_reply(sess["kind"], turn)
    else:
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
        reply = provider.generate(convo + "\nassistant:", system=sess["system_prompt"],
                                  max_tokens=400).text
    transcript.append({"role": "assistant", "content": reply, "ts": _now()})

    conn.execute("UPDATE conversation_sessions SET transcript = ?, turn_count = ? WHERE id = ?",
                 (json.dumps(transcript), turn, sid))
    conn.commit()
    return {"reply": reply, "turn_count": turn,
            "ready_to_complete": turn >= sess["target_turns"]}


def complete(conn: sqlite3.Connection, sim: sqlite3.Row, sid: str, student_id: str) -> dict:
    sess = _session(conn, sid)
    if sess["student_id"] != student_id:
        raise ConversationError("not your conversation", status=403)
    if sess["status"] == "completed":
        return {"already_completed": True, "assessment": sess.get("assessment")}

    provider, spec = get_provider(None)
    content = "\n".join(f"{m['role']}: {m['content']}" for m in sess["transcript"])
    result = assess(provider, spec, content=content, kind=sess["kind"])

    conn.execute("UPDATE conversation_sessions SET status = 'completed', assessment_json = ?, "
                 "completed_at = ? WHERE id = ?",
                 (json.dumps(result.to_dict()), _now(), sid))
    conn.commit()

    # Surface → event → workflow advance (the loop).
    advanced = None
    if sess["on_complete_event"] and sess["application_id"]:
        app = conn.execute("SELECT * FROM applications WHERE id = ?",
                           (sess["application_id"],)).fetchone()
        if app is not None:
            advanced = wfr.advance(conn, sim, dict(app), sess["on_complete_event"],
                                   {"outcome": result.outcome, "score": result.score})
    notify(conn, student_id=student_id, simulation_id=sim["id"],
           application_id=sess["application_id"], subject="Conversation assessed",
           body=f"Your {sess['kind'].replace('_', ' ')} is complete. {result.feedback}")
    return {"assessment": result.to_dict(), "advanced": advanced}


def get(conn: sqlite3.Connection, sim: sqlite3.Row, sid: str, student_id: str) -> dict:
    sess = _session(conn, sid)
    if sess["student_id"] != student_id:
        raise ConversationError("not your conversation", status=403)
    sess.pop("system_prompt", None)  # don't leak the persona's system prompt
    return sess
