"""The Ensayo FastAPI application (modular monolith — docs/adr/0002).

Routes are grouped by surface. Phase 3 (this increment) covers UC auth,
simulation create/list/generate/publish, and shared-password student verify, plus
serving the dashboard (/admin/) and generated sites (/sims/<slug>/) for local use.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import __version__
from ..config import ConfigError
from .auth import (
    create_token,
    current_uc,
    get_conn,
    get_uc_by_email,
    verify_password,
)
from .db import init_db
from .service import (
    ServiceError,
    add_visibility_rule,
    availability,
    cancel_booking,
    connect_repo,
    create_booking,
    create_simulation,
    delete_visibility_rule,
    evaluate_visibility,
    list_bookings,
    list_visibility_rules,
    publish,
    regenerate,
    row_to_dict,
    update_simulation,
    working_root,
)

_STATIC = Path(__file__).resolve().parent / "static"


# --- request models --------------------------------------------------------

class LoginReq(BaseModel):
    email: str
    password: str


class CreateSimReq(BaseModel):
    name: str
    company_yaml: str
    shared_password: str | None = None
    with_llm: bool = False
    build: bool = True


class GenerateReq(BaseModel):
    with_llm: bool = False
    build: bool = True


class StudentVerifyReq(BaseModel):
    slug: str
    password: str


class UpdateSimReq(BaseModel):
    company_yaml: str
    with_llm: bool = False
    build: bool = True


class ConnectRepoReq(BaseModel):
    repo_url: str = ""
    create_name: str = ""


class BookingReq(BaseModel):
    employee_slug: str
    slot_start: str
    student_name: str = ""
    student_email: str = ""


class VisibilityReq(BaseModel):
    target_type: str
    target_id: str
    action: str = "hide"
    trigger_type: str = "always"
    trigger_value: str = ""
    unit_code: str = ""


def create_app() -> FastAPI:
    app = FastAPI(title="Ensayo", version=__version__)
    app.state.conn = init_db()

    def _owned_sim(sim_id: str, uc: sqlite3.Row, conn: sqlite3.Connection) -> sqlite3.Row:
        sim = conn.execute("SELECT * FROM simulations WHERE id = ?", (sim_id,)).fetchone()
        if sim is None:
            raise HTTPException(404, "simulation not found")
        if sim["owner_uc_id"] != uc["id"] and uc["role"] != "instance_admin":
            raise HTTPException(403, "not your simulation")
        return sim

    def _sim_by_slug(slug: str, conn: sqlite3.Connection) -> sqlite3.Row:
        sim = conn.execute("SELECT * FROM simulations WHERE slug = ?", (slug,)).fetchone()
        if sim is None:
            raise HTTPException(404, "simulation not found")
        return sim

    # --- health ------------------------------------------------------------
    @app.get("/healthz")
    def healthz():
        return {"ok": True, "version": __version__}

    # --- UC auth -----------------------------------------------------------
    @app.post("/api/v1/auth/login")
    def login(req: LoginReq, conn: sqlite3.Connection = Depends(get_conn)):
        uc = get_uc_by_email(conn, req.email)
        if uc is None or not verify_password(req.password, uc["password_hash"]):
            raise HTTPException(401, "invalid email or password")
        conn.execute("UPDATE uc_accounts SET last_login_at = ? WHERE id = ?",
                     (datetime.now(timezone.utc).isoformat(), uc["id"]))
        conn.commit()
        return {"token": create_token(uc["id"]),
                "uc": {"id": uc["id"], "email": uc["email"],
                       "display_name": uc["display_name"], "role": uc["role"]}}

    @app.get("/api/v1/auth/me")
    def me(uc: sqlite3.Row = Depends(current_uc)):
        return {"id": uc["id"], "email": uc["email"],
                "display_name": uc["display_name"], "role": uc["role"]}

    # --- simulations -------------------------------------------------------
    @app.post("/api/v1/simulations", status_code=201)
    def create_sim(req: CreateSimReq, uc: sqlite3.Row = Depends(current_uc),
                   conn: sqlite3.Connection = Depends(get_conn)):
        try:
            return create_simulation(
                conn, uc["id"], req.name, req.company_yaml,
                shared_password=req.shared_password, with_llm=req.with_llm,
                build=req.build)
        except ConfigError as exc:
            raise HTTPException(422, f"invalid company.yaml:\n{exc}") from exc
        except ServiceError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/v1/simulations")
    def list_sims(uc: sqlite3.Row = Depends(current_uc),
                  conn: sqlite3.Connection = Depends(get_conn)):
        rows = conn.execute(
            "SELECT * FROM simulations WHERE owner_uc_id = ? ORDER BY updated_at DESC",
            (uc["id"],)).fetchall()
        return [row_to_dict(r) for r in rows]

    @app.get("/api/v1/simulations/{sim_id}")
    def get_sim(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                conn: sqlite3.Connection = Depends(get_conn)):
        return row_to_dict(_owned_sim(sim_id, uc, conn))

    @app.get("/api/v1/simulations/{sim_id}/yaml")
    def get_sim_yaml(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                     conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        path = Path(sim["working_clone_path"]) / "company.yaml"
        if not path.exists():
            raise HTTPException(404, "company.yaml not found")
        return {"company_yaml": path.read_text(encoding="utf-8")}

    @app.post("/api/v1/simulations/{sim_id}/generate")
    def generate_sim(sim_id: str, req: GenerateReq,
                     uc: sqlite3.Row = Depends(current_uc),
                     conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        try:
            return regenerate(conn, sim, with_llm=req.with_llm, build=req.build)
        except ServiceError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.put("/api/v1/simulations/{sim_id}")
    def update_sim(sim_id: str, req: UpdateSimReq,
                   uc: sqlite3.Row = Depends(current_uc),
                   conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        try:
            return update_simulation(conn, sim, req.company_yaml,
                                     with_llm=req.with_llm, build=req.build)
        except ConfigError as exc:
            raise HTTPException(422, f"invalid company.yaml:\n{exc}") from exc
        except ServiceError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/v1/simulations/{sim_id}/repo")
    def connect_sim_repo(sim_id: str, req: ConnectRepoReq,
                         uc: sqlite3.Row = Depends(current_uc),
                         conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        try:
            return connect_repo(conn, sim, repo_url=req.repo_url, create_name=req.create_name)
        except ServiceError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/v1/simulations/{sim_id}/publish")
    def publish_sim(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                    conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        try:
            return publish(conn, sim)
        except ServiceError as exc:
            raise HTTPException(400, str(exc)) from exc

    # --- booking (UC management) ------------------------------------------
    @app.get("/api/v1/simulations/{sim_id}/bookings")
    def sim_bookings(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                     conn: sqlite3.Connection = Depends(get_conn)):
        return list_bookings(conn, _owned_sim(sim_id, uc, conn))

    @app.post("/api/v1/simulations/{sim_id}/bookings/{booking_id}/cancel")
    def cancel_sim_booking(sim_id: str, booking_id: str,
                           uc: sqlite3.Row = Depends(current_uc),
                           conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        try:
            return cancel_booking(conn, sim, booking_id)
        except ServiceError as exc:
            raise HTTPException(404, str(exc)) from exc

    # --- visibility rules (UC management) ---------------------------------
    @app.get("/api/v1/simulations/{sim_id}/visibility")
    def sim_visibility(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                       conn: sqlite3.Connection = Depends(get_conn)):
        return list_visibility_rules(conn, _owned_sim(sim_id, uc, conn))

    @app.post("/api/v1/simulations/{sim_id}/visibility", status_code=201)
    def add_sim_visibility(sim_id: str, req: VisibilityReq,
                           uc: sqlite3.Row = Depends(current_uc),
                           conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        try:
            return add_visibility_rule(
                conn, sim, target_type=req.target_type, target_id=req.target_id,
                action=req.action, trigger_type=req.trigger_type,
                trigger_value=req.trigger_value, unit_code=req.unit_code)
        except ServiceError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.delete("/api/v1/simulations/{sim_id}/visibility/{rule_id}")
    def del_sim_visibility(sim_id: str, rule_id: str,
                           uc: sqlite3.Row = Depends(current_uc),
                           conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        try:
            return delete_visibility_rule(conn, sim, rule_id)
        except ServiceError as exc:
            raise HTTPException(404, str(exc)) from exc

    # --- student auth (shared password) -----------------------------------
    @app.post("/api/v1/auth/student/verify")
    def student_verify(req: StudentVerifyReq, conn: sqlite3.Connection = Depends(get_conn)):
        sim = conn.execute("SELECT * FROM simulations WHERE slug = ?", (req.slug,)).fetchone()
        if sim is None:
            raise HTTPException(404, "simulation not found")
        ph = sim["shared_password_hash"]
        ok = bool(ph) and verify_password(req.password, ph)
        return {"ok": ok}

    # --- student-facing booking + visibility (by slug; no UC auth) ---------
    @app.get("/api/v1/sims/{slug}/availability")
    def student_availability(slug: str, employee: str, date: str,
                             conn: sqlite3.Connection = Depends(get_conn)):
        sim = _sim_by_slug(slug, conn)
        try:
            return {"slots": availability(conn, sim, employee, date)}
        except ServiceError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/v1/sims/{slug}/bookings", status_code=201)
    def student_book(slug: str, req: BookingReq,
                     conn: sqlite3.Connection = Depends(get_conn)):
        sim = _sim_by_slug(slug, conn)
        try:
            return create_booking(conn, sim, req.employee_slug, req.slot_start,
                                  student_name=req.student_name,
                                  student_email=req.student_email)
        except ServiceError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/v1/sims/{slug}/visibility")
    def student_visibility(slug: str, unit_code: str = "",
                           conn: sqlite3.Connection = Depends(get_conn)):
        sim = _sim_by_slug(slug, conn)
        return evaluate_visibility(conn, sim, unit_code=unit_code)

    # --- serve generated sites (local; GitHub Pages in production) ---------
    @app.get("/sims/{slug}")
    def sim_root(slug: str):
        return RedirectResponse(url=f"/sims/{slug}/")

    @app.get("/sims/{slug}/{path:path}")
    def serve_sim(slug: str, path: str):
        root = (working_root() / slug / "dist").resolve()
        if not root.exists():
            raise HTTPException(404, "site not built")
        candidate = (root / path).resolve()
        if not str(candidate).startswith(str(root)):
            raise HTTPException(403, "forbidden")
        if path == "" or candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.exists():
            raise HTTPException(404, "not found")
        return FileResponse(candidate)

    # --- dashboard + root --------------------------------------------------
    app.mount("/admin", StaticFiles(directory=_STATIC / "admin", html=True), name="admin")

    @app.get("/")
    def root():
        return RedirectResponse(url="/admin/")

    return app

