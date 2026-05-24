"""Workflow runtime: drive a student's application through workflow stages.

Wires the declarative engine (``ensayo.workflow``, ADR-0008) into per-student
state. An **application** is a student's run through a simulation's workflow; each
stage transition dispatches the new stage's ``on_enter`` actions through the
notify adapter. Events come from outside (surface handlers, or an instructor) —
the workflow only routes.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from ..workflow import Workflow, WorkflowError, load_workflow
from .notify import notify


class WorkflowRuntimeError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workflow(sim: sqlite3.Row) -> Workflow:
    name = sim["workflow"]
    if not name:
        raise WorkflowRuntimeError("this simulation has no workflow configured")
    try:
        return load_workflow(name)
    except WorkflowError as exc:
        raise WorkflowRuntimeError(f"workflow {name!r} could not be loaded: {exc}") from exc


def _row(conn: sqlite3.Connection, app_id: str) -> dict:
    return dict(conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone())


def start_application(conn: sqlite3.Connection, sim: sqlite3.Row, student_id: str,
                     company_slug: str = "", job_title: str = "") -> dict:
    wf = _workflow(sim)
    dup = conn.execute(
        "SELECT 1 FROM applications WHERE simulation_id = ? AND student_id = ? "
        "AND company_slug = ? AND status = 'active'",
        (sim["id"], student_id, company_slug)).fetchone()
    if dup:
        raise WorkflowRuntimeError("you already have an active application here", status=409)

    aid = str(uuid.uuid4())
    now = _now()
    conn.execute(
        "INSERT INTO applications (id, simulation_id, student_id, company_slug, "
        "job_title, current_stage, status, cycle, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?, 'active', 1, ?, ?)",
        (aid, sim["id"], student_id, company_slug, job_title, wf.initial_stage, now, now))
    conn.commit()
    app = _row(conn, aid)
    _dispatch(conn, sim, app, wf.stage(wf.initial_stage).on_enter)
    return app


def advance(conn: sqlite3.Connection, sim: sqlite3.Row, app: dict, event: str,
            context: dict | None = None) -> dict:
    wf = _workflow(sim)
    if app["status"] != "active":
        return {"advanced": False, "reason": "application is not active",
                "stage": app["current_stage"]}
    res = wf.advance(app["current_stage"], event, context or {})
    if res is None:
        return {"advanced": False,
                "reason": f"no transition for event {event!r} from stage "
                          f"{app['current_stage']!r}",
                "stage": app["current_stage"]}

    terminal = wf.is_terminal(res.to)
    status = "completed" if terminal else "active"
    if terminal and "reject" in res.to:
        status = "rejected"
    conn.execute("UPDATE applications SET current_stage = ?, status = ?, updated_at = ? "
                 "WHERE id = ?", (res.to, status, _now(), app["id"]))
    conn.commit()
    app = _row(conn, app["id"])
    _dispatch(conn, sim, app, res.actions)
    return {"advanced": True, "stage": res.to, "terminal": terminal, "status": status,
            "surfaces": wf.surfaces(res.to)}


def _dispatch(conn: sqlite3.Connection, sim: sqlite3.Row, app: dict, actions: list[dict]) -> None:
    """Carry out a stage's on_enter actions. Unknown action types are ignored
    (their surfaces arrive in later increments)."""
    for a in actions:
        kind = a.get("type")
        if kind == "notify":
            notify(conn, student_id=app["student_id"], simulation_id=sim["id"],
                   application_id=app["id"], subject=sim["name"],
                   body=a.get("message", ""), inbox="work")
        elif kind == "assign_tasks":
            notify(conn, student_id=app["student_id"], simulation_id=sim["id"],
                   application_id=app["id"], subject="Tasks assigned",
                   body="New tasks are available in your task list.", inbox="work")


def get_application(conn: sqlite3.Connection, sim: sqlite3.Row, app_id: str) -> dict:
    row = conn.execute("SELECT * FROM applications WHERE id = ? AND simulation_id = ?",
                       (app_id, sim["id"])).fetchone()
    if row is None:
        raise WorkflowRuntimeError("application not found", status=404)
    return dict(row)


def list_applications(conn: sqlite3.Connection, sim: sqlite3.Row,
                      student_id: str | None = None) -> list[dict]:
    if student_id:
        rows = conn.execute("SELECT * FROM applications WHERE simulation_id = ? "
                            "AND student_id = ? ORDER BY created_at",
                            (sim["id"], student_id)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM applications WHERE simulation_id = ? "
                            "ORDER BY created_at", (sim["id"],)).fetchall()
    return [dict(r) for r in rows]


def list_messages(conn: sqlite3.Connection, sim: sqlite3.Row, student_id: str,
                  inbox: str | None = None) -> list[dict]:
    """Inbox messages whose lazy-delivery time has passed (ADR-0007)."""
    q = ("SELECT * FROM messages WHERE simulation_id = ? AND student_id = ? "
         "AND deliver_at <= ?")
    params: list = [sim["id"], student_id, _now()]
    if inbox:
        q += " AND inbox = ?"
        params.append(inbox)
    q += " ORDER BY deliver_at DESC"
    return [dict(r) for r in conn.execute(q, params).fetchall()]


def mark_read(conn: sqlite3.Connection, sim: sqlite3.Row, student_id: str,
              message_id: str) -> dict:
    cur = conn.execute(
        "UPDATE messages SET is_read = 1 WHERE id = ? AND simulation_id = ? AND student_id = ?",
        (message_id, sim["id"], student_id))
    conn.commit()
    if cur.rowcount == 0:
        raise WorkflowRuntimeError("message not found", status=404)
    return {"read": True, "id": message_id}
