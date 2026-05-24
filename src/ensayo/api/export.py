"""External-tool export endpoints (spec §15.1, Phase 8).

Stable JSON contracts (versioned with ``schema_version``) that any external tool —
a gradebook, an analytics dashboard, Talk Buddy — can consume. Read-only,
UC-scoped. PII handling is the deployer's responsibility (these expose student
identifiers for the owning UC).
"""

from __future__ import annotations

import json
import sqlite3

SCHEMA_VERSION = "1.0"


def _loads(s: str | None, default):
    try:
        return json.loads(s) if s else default
    except (json.JSONDecodeError, TypeError):
        return default


def export_applications(conn: sqlite3.Connection, sim: sqlite3.Row) -> dict:
    rows = conn.execute("SELECT * FROM applications WHERE simulation_id = ? ORDER BY created_at",
                        (sim["id"],)).fetchall()
    return {"schema_version": SCHEMA_VERSION, "simulation": sim["slug"],
            "applications": [
                {"id": r["id"], "student_id": r["student_id"], "company": r["company_slug"],
                 "job_title": r["job_title"], "stage": r["current_stage"],
                 "status": r["status"], "cycle": r["cycle"],
                 "created_at": r["created_at"], "updated_at": r["updated_at"]}
                for r in rows]}


def export_conversations(conn: sqlite3.Connection, sim: sqlite3.Row) -> dict:
    rows = conn.execute("SELECT * FROM conversation_sessions WHERE simulation_id = ? "
                        "ORDER BY created_at", (sim["id"],)).fetchall()
    return {"schema_version": SCHEMA_VERSION, "simulation": sim["slug"],
            "conversations": [
                {"id": r["id"], "student_id": r["student_id"], "kind": r["kind"],
                 "persona": r["persona_slug"], "status": r["status"],
                 "turns": r["turn_count"], "transcript": _loads(r["transcript"], []),
                 "assessment": _loads(r["assessment_json"], None),
                 "created_at": r["created_at"], "completed_at": r["completed_at"]}
                for r in rows]}


def export_journey(conn: sqlite3.Connection, sim: sqlite3.Row, student_id: str) -> dict:
    """One student's full journey across all surfaces — the journey report data."""
    sid = sim["id"]
    apps = conn.execute("SELECT * FROM applications WHERE simulation_id = ? AND student_id = ? "
                        "ORDER BY created_at", (sid, student_id)).fetchall()
    convos = conn.execute("SELECT * FROM conversation_sessions WHERE simulation_id = ? AND "
                          "student_id = ? ORDER BY created_at", (sid, student_id)).fetchall()
    subs = conn.execute("SELECT * FROM doc_submissions WHERE simulation_id = ? AND "
                        "student_id = ? ORDER BY created_at", (sid, student_id)).fetchall()
    return {
        "schema_version": SCHEMA_VERSION, "simulation": sim["slug"], "student_id": student_id,
        "applications": [{"id": a["id"], "company": a["company_slug"],
                          "stage": a["current_stage"], "status": a["status"]} for a in apps],
        "conversations": [{"id": c["id"], "kind": c["kind"], "status": c["status"],
                           "assessment": _loads(c["assessment_json"], None)} for c in convos],
        "submissions": [{"id": s["id"], "title": s["title"], "outcome": s["outcome"],
                         "score": s["score"]} for s in subs],
    }


def export_cohort(conn: sqlite3.Connection, sim: sqlite3.Row) -> dict:
    """Aggregate cohort summary (no per-student transcripts)."""
    sid = sim["id"]

    def counts(table: str, col: str) -> dict:
        rows = conn.execute(f"SELECT {col} k, COUNT(*) n FROM {table} "
                            f"WHERE simulation_id = ? GROUP BY {col}", (sid,)).fetchall()
        return {r["k"]: r["n"] for r in rows}

    students = conn.execute("SELECT COUNT(*) n FROM student_access WHERE simulation_id = ? "
                            "AND status != 'deleted'", (sid,)).fetchone()["n"]
    return {
        "schema_version": SCHEMA_VERSION, "simulation": sim["slug"],
        "students": students,
        "applications_by_stage": counts("applications", "current_stage"),
        "applications_by_status": counts("applications", "status"),
        "conversations_by_status": counts("conversation_sessions", "status"),
        "submissions_by_outcome": counts("doc_submissions", "outcome"),
    }
