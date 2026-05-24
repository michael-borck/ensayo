"""UC-facing student management: roster, whitelist, reset, soft-delete, export, metrics."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from .auth import hash_password
from .studentauth import StudentError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _booking_counts(conn: sqlite3.Connection, sim_id: str) -> dict[str, int]:
    rows = conn.execute(
        "SELECT student_email, COUNT(*) n FROM bookings WHERE simulation_id = ? "
        "AND status = 'confirmed' AND student_email != '' GROUP BY student_email",
        (sim_id,)).fetchall()
    return {r["student_email"]: r["n"] for r in rows}


def list_students(conn: sqlite3.Connection, sim: sqlite3.Row) -> list[dict]:
    counts = _booking_counts(conn, sim["id"])
    rows = conn.execute(
        "SELECT * FROM student_access WHERE simulation_id = ? ORDER BY created_at",
        (sim["id"],)).fetchall()
    return [{
        "id": r["id"], "email": r["email"], "name": r["name"], "status": r["status"],
        "auth_mode": r["auth_mode"], "created_at": r["created_at"],
        "first_access_at": r["first_access_at"], "last_access_at": r["last_access_at"],
        "deleted_at": r["deleted_at"],
        "bookings": counts.get(r["email"] or "", 0),
    } for r in rows]


def metrics(conn: sqlite3.Connection, sim: sqlite3.Row) -> dict:
    rows = list_students(conn, sim)
    active = [r for r in rows if r["status"] == "active"]
    return {
        "total": len(rows),
        "active": len(active),
        "deleted": sum(1 for r in rows if r["status"] == "deleted"),
        "ever_accessed": sum(1 for r in rows if r["first_access_at"]),
        "total_bookings": sum(r["bookings"] for r in rows),
    }


def add_whitelist(conn: sqlite3.Connection, sim: sqlite3.Row, emails: list[str]) -> dict:
    added = 0
    for raw in emails:
        email = raw.strip().lower()
        if not email or "@" not in email:
            continue
        try:
            conn.execute(
                "INSERT INTO student_whitelist (id, simulation_id, email, created_at) "
                "VALUES (?,?,?,?)", (str(uuid.uuid4()), sim["id"], email, _now()))
            added += 1
        except sqlite3.IntegrityError:
            pass  # already whitelisted
    conn.commit()
    total = conn.execute("SELECT COUNT(*) n FROM student_whitelist WHERE simulation_id = ?",
                         (sim["id"],)).fetchone()["n"]
    return {"added": added, "total": total}


def list_whitelist(conn: sqlite3.Connection, sim: sqlite3.Row) -> list[str]:
    return [r["email"] for r in conn.execute(
        "SELECT email FROM student_whitelist WHERE simulation_id = ? ORDER BY email",
        (sim["id"],)).fetchall()]


def parse_whitelist_csv(text: str) -> list[str]:
    """Extract emails from CSV/plain text (one per line or comma-separated, header ok)."""
    import csv
    import io
    emails: list[str] = []
    for row in csv.reader(io.StringIO(text)):
        for cell in row:
            cell = cell.strip()
            if "@" in cell and "." in cell:
                emails.append(cell)
    return emails


def uc_reset_password(conn: sqlite3.Connection, sim: sqlite3.Row, student_id: str,
                      new_password: str) -> dict:
    s = conn.execute("SELECT * FROM student_access WHERE id = ? AND simulation_id = ?",
                     (student_id, sim["id"])).fetchone()
    if s is None:
        raise StudentError("student not found", status=404)
    if not new_password:
        raise StudentError("new password is required")
    conn.execute("UPDATE student_access SET password_hash = ?, reset_code = '', "
                 "reset_expires = '' WHERE id = ?", (hash_password(new_password), student_id))
    conn.commit()
    return {"reset": True, "id": student_id}


def soft_delete(conn: sqlite3.Connection, sim: sqlite3.Row, student_id: str) -> dict:
    """Soft delete (spec §6.7): redact PII, keep the row + anonymise bookings."""
    s = conn.execute("SELECT * FROM student_access WHERE id = ? AND simulation_id = ?",
                     (student_id, sim["id"])).fetchone()
    if s is None:
        raise StudentError("student not found", status=404)
    if s["email"]:
        conn.execute("UPDATE bookings SET student_name = '[redacted]', "
                     "student_email = '[redacted]' WHERE simulation_id = ? AND student_email = ?",
                     (sim["id"], s["email"]))
    conn.execute(
        "UPDATE student_access SET status = 'deleted', deleted_at = ?, email = NULL, "
        "name = '', password_hash = '', reset_code = '', reset_expires = '' WHERE id = ?",
        (_now(), student_id))
    conn.commit()
    return {"deleted": True, "id": student_id}


def export_students(conn: sqlite3.Connection, sim: sqlite3.Row) -> str:
    """Return the roster as CSV text (PII export — UC responsibility, spec §6.7)."""
    import csv
    import io
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "email", "name", "status", "created_at", "first_access_at",
                "last_access_at", "bookings"])
    for r in list_students(conn, sim):
        w.writerow([r["id"], r["email"] or "", r["name"] or "", r["status"],
                    r["created_at"], r["first_access_at"] or "", r["last_access_at"] or "",
                    r["bookings"]])
    return out.getvalue()
