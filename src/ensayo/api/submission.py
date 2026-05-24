"""Document submission surface (spec §12).

A student submits written work; it's assessed (reusing assess.py); the feedback is
**lazy-gated** — hidden as "under review" until ``review_deliver_at`` passes
(ADR-0007) — and a passing submission emits a workflow event to advance the
application. Stub-backed so it runs offline.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from ..assess import assess
from ..llm import get_provider
from . import workflow_runtime as wfr
from .notify import notify


class SubmissionError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def submit(conn: sqlite3.Connection, sim: sqlite3.Row, student_id: str, *, title: str,
           body: str, application_id: str | None = None, on_complete_event: str = "",
           review_delay_seconds: int = 0) -> dict:
    if not body.strip():
        raise SubmissionError("submission is empty")

    provider, spec = get_provider(None)
    result = assess(provider, spec, content=body, kind="document_submission",
                    rubric=title)
    deliver_at = (_now() + timedelta(seconds=review_delay_seconds)).isoformat()

    sid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO doc_submissions (id, simulation_id, student_id, application_id, "
        "title, body, score, feedback, focus_areas, outcome, status, on_complete_event, "
        "review_deliver_at, created_at, reviewed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?, 'reviewed', ?, ?, ?, ?)",
        (sid, sim["id"], student_id, application_id, title, body, result.score,
         result.feedback, json.dumps(result.focus_areas), result.outcome,
         on_complete_event, deliver_at, _now().isoformat(), _now().isoformat()))
    conn.commit()

    advanced = None
    if result.outcome == "pass" and on_complete_event and application_id:
        app = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
        if app is not None:
            advanced = wfr.advance(conn, sim, dict(app), on_complete_event,
                                   {"outcome": result.outcome, "score": result.score})
    notify(conn, student_id=student_id, simulation_id=sim["id"], application_id=application_id,
           subject="Submission received",
           body=f"Your submission '{title}' is under review.", deliver_at=None)
    return {**_public(conn, sid), "advanced": advanced}


def _public(conn: sqlite3.Connection, sid: str) -> dict:
    return _gate(dict(conn.execute("SELECT * FROM doc_submissions WHERE id = ?", (sid,)).fetchone()))


def _gate(row: dict) -> dict:
    """Hide the review until its lazy-delivery time has passed."""
    delivered = _now() >= datetime.fromisoformat(row["review_deliver_at"])
    out = {"id": row["id"], "title": row["title"], "status": row["status"],
           "outcome": row["outcome"] if delivered else None,
           "created_at": row["created_at"], "review_available": delivered}
    if delivered:
        out["score"] = row["score"]
        out["feedback"] = row["feedback"]
        out["focus_areas"] = json.loads(row["focus_areas"] or "[]")
    else:
        out["status"] = "under_review"
    return out


def list_submissions(conn: sqlite3.Connection, sim: sqlite3.Row, student_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM doc_submissions WHERE simulation_id = ? AND "
                        "student_id = ? ORDER BY created_at DESC",
                        (sim["id"], student_id)).fetchall()
    return [_gate(dict(r)) for r in rows]


def get_submission(conn: sqlite3.Connection, sim: sqlite3.Row, student_id: str,
                   sid: str) -> dict:
    row = conn.execute("SELECT * FROM doc_submissions WHERE id = ? AND simulation_id = ? "
                       "AND student_id = ?", (sid, sim["id"], student_id)).fetchone()
    if row is None:
        raise SubmissionError("submission not found", status=404)
    return _gate(dict(row))
