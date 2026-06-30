"""The Ensayo FastAPI application (modular monolith — docs/adr/0002).

Routes are grouped by surface. Phase 3 (this increment) covers UC auth,
simulation create/list/generate/publish, and shared-password student verify, plus
serving the dashboard (/admin/) and generated sites (/sims/<slug>/) for local use.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import conversation as convo
from . import export as export_svc
from . import groupchat as gchat
from . import students as student_mgmt
from . import studentauth
from . import submission as subm
from . import workflow_runtime as wfr

from .. import __version__
from ..config import ConfigError, load_company_config
from ..safemode import audience_report
from .auth import (
    create_token,
    current_uc,
    get_conn,
    get_uc_by_email,
    verify_password,
)
from .db import init_db
from . import registration as reg
from .ratelimit import check as rate_check
from .provision import provision_chatbots
from .service import (
    ServiceError,
    add_visibility_rule,
    availability,
    cancel_booking,
    connect_repo,
    create_booking,
    create_multisite_simulation,
    create_simulation,
    delete_simulation,
    delete_visibility_rule,
    evaluate_visibility,
    list_bookings,
    list_visibility_rules,
    publish,
    regenerate,
    row_to_dict,
    sim_usage,
    update_multisite_simulation,
    update_simulation,
    working_root,
)

_STATIC = Path(__file__).resolve().parent / "static"


# --- request models --------------------------------------------------------

class LoginReq(BaseModel):
    email: str
    password: str


class RegisterReq(BaseModel):
    email: str
    password: str
    display_name: str = ""


class VerifyEmailReq(BaseModel):
    email: str
    code: str


class ResendReq(BaseModel):
    email: str


class RegistrationToggleReq(BaseModel):
    open: bool

class MaintenanceToggleReq(BaseModel):
    on: bool


class CreateSimReq(BaseModel):
    name: str
    company_yaml: str = ""          # raw YAML (advanced) …
    config: dict | None = None      # … or structured single-company fields
    simulation: dict | None = None  # … or structured multi-site config (portal + companies)
    shared_password: str | None = None
    auth_mode: str = "shared_password"
    workflow: str = ""
    with_llm: bool = False
    build: bool = True


class ApplicationReq(BaseModel):
    company_slug: str = ""
    job_title: str = ""


class AdvanceReq(BaseModel):
    event: str
    context: dict = {}


class ConversationStartReq(BaseModel):
    kind: str = "conversation"
    persona_slug: str
    persona_name: str = ""
    application_id: str | None = None
    on_complete_event: str = ""
    target_turns: int = 4


class ConversationMessageReq(BaseModel):
    text: str


class SubmissionReq(BaseModel):
    title: str = ""
    body: str
    application_id: str | None = None
    on_complete_event: str = ""
    review_delay_seconds: int = 0


class GroupChatStartReq(BaseModel):
    occasion: str = ""
    participants: list = []
    beats: list = []
    application_id: str | None = None
    beat_interval_seconds: int = 0


class GroupChatPostReq(BaseModel):
    text: str


class AuthModeReq(BaseModel):
    auth_mode: str
    shared_password: str | None = None


class StudentRegisterReq(BaseModel):
    email: str
    name: str = ""
    password: str


class StudentLoginReq(BaseModel):
    email: str
    password: str = ""


class ResetRequestReq(BaseModel):
    email: str


class ResetReq(BaseModel):
    email: str
    code: str
    new_password: str


class WhitelistReq(BaseModel):
    emails: list[str] = []
    csv: str = ""


class UcResetReq(BaseModel):
    new_password: str


class GenerateReq(BaseModel):
    with_llm: bool = False
    build: bool = True


class ProvisionReq(BaseModel):
    build: bool = True


class StudentVerifyReq(BaseModel):
    slug: str
    password: str


class UpdateSimReq(BaseModel):
    company_yaml: str = ""          # raw YAML (advanced) …
    config: dict | None = None      # … or structured single-company fields
    simulation: dict | None = None  # … or structured multi-site config
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
    def login(req: LoginReq, request: Request,
              conn: sqlite3.Connection = Depends(get_conn)):
        ip = request.client.host if request.client else None
        # Login is not IP-rate-limited (cohort NAT) — per-account lockout covers brute force.
        if reg.is_locked_out(conn, req.email):
            raise HTTPException(429, "account temporarily locked after repeated failures")
        uc = get_uc_by_email(conn, req.email)
        ok = uc is not None and verify_password(req.password, uc["password_hash"])
        reg.record_login_attempt(conn, req.email, ok, ip)
        if not ok:
            raise HTTPException(401, "invalid email or password")
        if not uc["is_verified"]:
            raise HTTPException(403, "email not verified — enter the code we sent, or request a new one")
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
    @app.post("/api/v1/auth/register", status_code=201)
    def register(req: RegisterReq,
                 conn: sqlite3.Connection = Depends(get_conn)):
        try:
            return reg.register(conn, req.email, req.password, req.display_name)
        except reg.RegistrationError as exc:
            raise HTTPException(exc.status, exc.message) from exc

    @app.post("/api/v1/auth/verify-email")
    def verify_email(req: VerifyEmailReq,
                     conn: sqlite3.Connection = Depends(get_conn)):
        if not rate_check("verify", req.email):
            raise HTTPException(429, "too many attempts — try again shortly")
        try:
            return reg.verify_email(conn, req.email, req.code)
        except reg.RegistrationError as exc:
            raise HTTPException(exc.status, exc.message) from exc

    @app.post("/api/v1/auth/resend-verification")
    def resend_verification(req: ResendReq,
                            conn: sqlite3.Connection = Depends(get_conn)):
        if not rate_check("resend", req.email):
            raise HTTPException(429, "too many resend attempts — try again shortly")
        return reg.resend_code(conn, req.email)

    @app.get("/api/v1/auth/registration-status")
    def registration_status(conn: sqlite3.Connection = Depends(get_conn)):
        # Public — lets the sign-up UI show/hide itself and warn when closed/email-less.
        return {"registration_open": reg.registration_open(conn),
                "allowed_domains": reg.allowed_domains(),
                "email_configured": reg.email_svc.configured()}

    # --- instance admin: users + registration control ---------------------
    def _require_admin(uc: sqlite3.Row) -> sqlite3.Row:
        if uc["role"] != "instance_admin":
            raise HTTPException(403, "instance admin only")
        return uc

    @app.get("/api/v1/admin/users")
    def admin_users(uc: sqlite3.Row = Depends(current_uc),
                    conn: sqlite3.Connection = Depends(get_conn)):
        _require_admin(uc)
        return reg.list_users(conn)

    @app.get("/api/v1/admin/pending-codes")
    def admin_pending_codes(uc: sqlite3.Row = Depends(current_uc),
                            conn: sqlite3.Connection = Depends(get_conn)):
        _require_admin(uc)
        return reg.pending_codes(conn)

    @app.put("/api/v1/admin/registration")
    def admin_toggle_registration(req: RegistrationToggleReq,
                                  uc: sqlite3.Row = Depends(current_uc),
                                  conn: sqlite3.Connection = Depends(get_conn)):
        _require_admin(uc)
        return {"registration_open": reg.set_registration_open(conn, req.open)}

    @app.put("/api/v1/admin/maintenance")
    def admin_toggle_maintenance(req: MaintenanceToggleReq,
                                uc: sqlite3.Row = Depends(current_uc),
                                conn: sqlite3.Connection = Depends(get_conn)):
        _require_admin(uc)
        return {"maintenance_mode": reg.set_maintenance_mode(conn, req.on)}

    # --- simulations -------------------------------------------------------
    @app.post("/api/v1/simulations", status_code=201)
    def create_sim(req: CreateSimReq, uc: sqlite3.Row = Depends(current_uc),
                   conn: sqlite3.Connection = Depends(get_conn)):
        # Multi-site (structured): portal + companies → simulation.yaml
        if req.simulation is not None:
            from ..config import dump_simulation_yaml
            from ..models import SimulationConfig
            try:
                simulation_yaml = dump_simulation_yaml(SimulationConfig.model_validate(req.simulation))
            except Exception as exc:
                raise HTTPException(422, f"invalid configuration: {exc}") from exc
            try:
                return create_multisite_simulation(
                    conn, uc["id"], req.name, simulation_yaml,
                    workflow=req.workflow, with_llm=req.with_llm, build=req.build)
            except ConfigError as exc:
                raise HTTPException(422, f"invalid simulation.yaml:\n{exc}") from exc
            except ServiceError as exc:
                raise HTTPException(400, str(exc)) from exc
        # Single-company (structured or raw YAML)
        company_yaml = req.company_yaml
        if req.config is not None:
            from ..config import dump_config_yaml
            from ..models import CompanyConfig
            try:
                company_yaml = dump_config_yaml(CompanyConfig.model_validate(req.config))
            except Exception as exc:  # pydantic ValidationError → 422
                raise HTTPException(422, f"invalid configuration: {exc}") from exc
        if not company_yaml.strip():
            raise HTTPException(422, "provide company_yaml, config, or simulation")
        try:
            return create_simulation(
                conn, uc["id"], req.name, company_yaml,
                shared_password=req.shared_password, auth_mode=req.auth_mode,
                workflow=req.workflow, with_llm=req.with_llm, build=req.build)
        except ConfigError as exc:
            raise HTTPException(422, f"invalid company.yaml:\n{exc}") from exc
        except ServiceError as exc:
            raise HTTPException(400, str(exc)) from exc

    # --- catalogs for the wizard (themes + archetypes) --------------------
    @app.get("/api/v1/themes")
    def list_theme_catalog(uc: sqlite3.Row = Depends(current_uc)):
        from ..themes import default_themes_dir, list_themes
        return [{"name": m.name, "description": m.description}
                for m in list_themes(default_themes_dir())
                if "company" in m.content_props]

    @app.get("/api/v1/archetypes")
    def list_archetype_catalog(uc: sqlite3.Row = Depends(current_uc)):
        from ..library import list_archetypes
        return [{"name": a.name, "label": a.label, "tier": a.default_tier,
                 "mature": a.mature} for a in list_archetypes()]

    @app.get("/api/v1/workflows")
    def list_workflow_catalog(uc: sqlite3.Row = Depends(current_uc)):
        from ..workflow import list_workflows, load_workflow
        out = []
        for name in list_workflows():
            try:
                out.append({"name": name, "description": load_workflow(name).description})
            except Exception:
                out.append({"name": name, "description": ""})
        return out

    @app.post("/api/v1/ideate")
    def ideate_endpoint(idea: str = Form(""),
                        file: UploadFile | None = File(None),
                        uc: sqlite3.Row = Depends(current_uc)):
        """Suggest 2-3 simulations from an idea and/or an uploaded file.

        The file is read in memory and discarded (never written to disk)."""
        from ..extract import ExtractError, extract_text
        from ..ideate import IdeateError, ideate
        content = ""
        if file is not None and file.filename:
            try:
                content = extract_text(file.file.read(), file.filename)
            except ExtractError as exc:
                raise HTTPException(exc.status, exc.message) from exc
        try:
            return {"proposals": ideate(idea, content)}
        except IdeateError as exc:
            raise HTTPException(exc.status, exc.message) from exc

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

    @app.get("/api/v1/simulations/{sim_id}/config")
    def get_sim_config(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                       conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        clone = Path(sim["working_clone_path"])
        try:
            if sim["type"] == "multi_site":
                from ..config import load_simulation_config
                return load_simulation_config(clone / "simulation.yaml").model_dump(mode="json")
            return load_company_config(clone / "company.yaml").model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(404, "config file not found") from exc
        except ConfigError as exc:
            raise HTTPException(422, str(exc)) from exc
    @app.delete("/api/v1/simulations/{sim_id}")
    def delete_sim(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                   conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        try:
            delete_simulation(conn, sim)
        except ServiceError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"deleted": True}
    @app.get("/api/v1/simulations/{sim_id}/audience")
    def sim_audience(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                     conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        path = Path(sim["working_clone_path"]) / "company.yaml"
        if not path.exists():
            raise HTTPException(404, "company.yaml not found")
        try:
            return audience_report(load_company_config(path))
        except ConfigError as exc:
            raise HTTPException(422, str(exc)) from exc

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
        # Multi-site (structured)
        if req.simulation is not None:
            from ..config import dump_simulation_yaml
            from ..models import SimulationConfig
            try:
                simulation_yaml = dump_simulation_yaml(SimulationConfig.model_validate(req.simulation))
            except Exception as exc:
                raise HTTPException(422, f"invalid configuration: {exc}") from exc
            try:
                return update_multisite_simulation(conn, sim, simulation_yaml,
                                                   with_llm=req.with_llm, build=req.build)
            except ConfigError as exc:
                raise HTTPException(422, f"invalid simulation.yaml:\n{exc}") from exc
            except ServiceError as exc:
                raise HTTPException(400, str(exc)) from exc
        # Single-company
        company_yaml = req.company_yaml
        if req.config is not None:  # structured editor → build YAML server-side
            from ..config import dump_config_yaml
            from ..models import CompanyConfig
            try:
                company_yaml = dump_config_yaml(CompanyConfig.model_validate(req.config))
            except Exception as exc:  # pydantic ValidationError → 422
                raise HTTPException(422, f"invalid configuration: {exc}") from exc
        if not company_yaml.strip():
            raise HTTPException(422, "provide company_yaml, config, or simulation")
        try:
            return update_simulation(conn, sim, company_yaml,
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

    @app.post("/api/v1/simulations/{sim_id}/provision-chatbots")
    def provision_sim(sim_id: str, req: ProvisionReq,
                      uc: sqlite3.Row = Depends(current_uc),
                      conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        try:
            return provision_chatbots(conn, sim, build=req.build)
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

    # --- auth mode (UC) ---------------------------------------------------
    @app.post("/api/v1/simulations/{sim_id}/auth-mode")
    def set_auth_mode(sim_id: str, req: AuthModeReq,
                      uc: sqlite3.Row = Depends(current_uc),
                      conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        if req.auth_mode not in ("shared_password", "individual_account", "email_only"):
            raise HTTPException(400, "invalid auth_mode")
        if sim["audience"] == "minors" and req.auth_mode != "shared_password":
            raise HTTPException(400, "minors-audience simulations must use shared_password")
        from .auth import hash_password
        ph = hash_password(req.shared_password) if req.shared_password else sim["shared_password_hash"]
        conn.execute("UPDATE simulations SET auth_mode = ?, shared_password_hash = ? WHERE id = ?",
                     (req.auth_mode, ph, sim_id))
        conn.commit()
        return {"auth_mode": req.auth_mode}

    # --- student management (UC) ------------------------------------------
    @app.get("/api/v1/simulations/{sim_id}/students")
    def list_sim_students(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                          conn: sqlite3.Connection = Depends(get_conn)):
        return student_mgmt.list_students(conn, _owned_sim(sim_id, uc, conn))

    @app.get("/api/v1/simulations/{sim_id}/students/metrics")
    def sim_student_metrics(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                            conn: sqlite3.Connection = Depends(get_conn)):
        return student_mgmt.metrics(conn, _owned_sim(sim_id, uc, conn))

    @app.get("/api/v1/simulations/{sim_id}/students/export")
    def export_sim_students(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                            conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        csv_text = student_mgmt.export_students(conn, sim)
        return Response(content=csv_text, media_type="text/csv",
                        headers={"Content-Disposition":
                                 f"attachment; filename={sim['slug']}-students.csv"})

    @app.get("/api/v1/simulations/{sim_id}/whitelist")
    def get_whitelist(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                      conn: sqlite3.Connection = Depends(get_conn)):
        return {"emails": student_mgmt.list_whitelist(conn, _owned_sim(sim_id, uc, conn))}

    @app.post("/api/v1/simulations/{sim_id}/whitelist")
    def post_whitelist(sim_id: str, req: WhitelistReq,
                       uc: sqlite3.Row = Depends(current_uc),
                       conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        emails = list(req.emails) + (student_mgmt.parse_whitelist_csv(req.csv) if req.csv else [])
        return student_mgmt.add_whitelist(conn, sim, emails)

    @app.post("/api/v1/simulations/{sim_id}/students/{student_id}/reset-password")
    def uc_reset_student(sim_id: str, student_id: str, req: UcResetReq,
                         uc: sqlite3.Row = Depends(current_uc),
                         conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        try:
            return student_mgmt.uc_reset_password(conn, sim, student_id, req.new_password)
        except studentauth.StudentError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    @app.delete("/api/v1/simulations/{sim_id}/students/{student_id}")
    def delete_sim_student(sim_id: str, student_id: str,
                           uc: sqlite3.Row = Depends(current_uc),
                           conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        try:
            return student_mgmt.soft_delete(conn, sim, student_id)
        except studentauth.StudentError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    # --- student-facing auth (by slug) ------------------------------------
    @app.post("/api/v1/sims/{slug}/students/register", status_code=201)
    def student_register(slug: str, req: StudentRegisterReq,
                         conn: sqlite3.Connection = Depends(get_conn)):
        sim = _sim_by_slug(slug, conn)
        try:
            return studentauth.register(conn, sim, req.email, req.name, req.password)
        except studentauth.StudentError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    @app.post("/api/v1/sims/{slug}/students/login")
    def student_login(slug: str, req: StudentLoginReq,
                      conn: sqlite3.Connection = Depends(get_conn)):
        sim = _sim_by_slug(slug, conn)
        try:
            student, token = studentauth.login(conn, sim, req.email, req.password)
            return {"student": student, "token": token}
        except studentauth.StudentError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    @app.post("/api/v1/sims/{slug}/students/request-reset")
    def student_request_reset(slug: str, req: ResetRequestReq,
                              conn: sqlite3.Connection = Depends(get_conn)):
        return studentauth.request_reset(conn, _sim_by_slug(slug, conn), req.email)

    @app.post("/api/v1/sims/{slug}/students/reset")
    def student_reset(slug: str, req: ResetReq,
                      conn: sqlite3.Connection = Depends(get_conn)):
        sim = _sim_by_slug(slug, conn)
        try:
            return studentauth.reset(conn, sim, req.email, req.code, req.new_password)
        except studentauth.StudentError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    @app.get("/api/v1/sims/{slug}/students/me")
    def student_me(slug: str, student: dict = Depends(studentauth.current_student),
                   conn: sqlite3.Connection = Depends(get_conn)):
        row = conn.execute("SELECT * FROM student_access WHERE id = ?",
                           (student["id"],)).fetchone()
        if row is None or row["deleted_at"] is not None:
            raise HTTPException(401, "account not found")
        return {"id": row["id"], "email": row["email"], "name": row["name"]}

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

    @app.get("/api/v1/sims/{slug}/employees")
    def sim_employees(slug: str, conn: sqlite3.Connection = Depends(get_conn)):
        sim = _sim_by_slug(slug, conn)
        cache = json.loads(sim["config_cache"] or "{}")
        emps = list(cache.get("employees", []))
        for c in cache.get("companies", []):  # multi-site: flatten company employees
            emps.extend(c.get("employees", []))
        return [{"slug": e.get("id") or e.get("slug"), "name": e.get("name", ""),
                 "role": e.get("role", "")} for e in emps]

    # --- workflow runtime: student applications + inbox -------------------
    def _student_sim(slug: str, student: dict, conn: sqlite3.Connection) -> sqlite3.Row:
        if student["slug"] != slug:
            raise HTTPException(403, "token is for a different simulation")
        return _sim_by_slug(slug, conn)

    @app.post("/api/v1/sims/{slug}/applications", status_code=201)
    def student_apply(slug: str, req: ApplicationReq,
                      student: dict = Depends(studentauth.current_student),
                      conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        try:
            return wfr.start_application(conn, sim, student["id"],
                                        company_slug=req.company_slug, job_title=req.job_title)
        except wfr.WorkflowRuntimeError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    @app.get("/api/v1/sims/{slug}/applications")
    def student_applications(slug: str,
                             student: dict = Depends(studentauth.current_student),
                             conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        return wfr.list_applications(conn, sim, student_id=student["id"])

    @app.get("/api/v1/sims/{slug}/messages")
    def student_messages(slug: str, inbox: str = "",
                         student: dict = Depends(studentauth.current_student),
                         conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        return wfr.list_messages(conn, sim, student["id"], inbox=inbox or None)

    @app.post("/api/v1/sims/{slug}/messages/{message_id}/read")
    def student_mark_read(slug: str, message_id: str,
                          student: dict = Depends(studentauth.current_student),
                          conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        try:
            return wfr.mark_read(conn, sim, student["id"], message_id)
        except wfr.WorkflowRuntimeError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    # --- 1-on-1 conversation surface --------------------------------------
    @app.post("/api/v1/sims/{slug}/conversations", status_code=201)
    def conversation_start(slug: str, req: ConversationStartReq,
                           student: dict = Depends(studentauth.current_student),
                           conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        try:
            return convo.start(conn, sim, student["id"], kind=req.kind,
                               persona_slug=req.persona_slug, persona_name=req.persona_name,
                               application_id=req.application_id,
                               on_complete_event=req.on_complete_event,
                               target_turns=req.target_turns)
        except convo.ConversationError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    @app.get("/api/v1/sims/{slug}/conversations/{sid}")
    def conversation_get(slug: str, sid: str,
                         student: dict = Depends(studentauth.current_student),
                         conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        try:
            return convo.get(conn, sim, sid, student["id"])
        except convo.ConversationError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    @app.post("/api/v1/sims/{slug}/conversations/{sid}/message")
    def conversation_message(slug: str, sid: str, req: ConversationMessageReq,
                             student: dict = Depends(studentauth.current_student),
                             conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        try:
            return convo.send_message(conn, sim, sid, student["id"], req.text)
        except convo.ConversationError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    @app.post("/api/v1/sims/{slug}/conversations/{sid}/complete")
    def conversation_complete(slug: str, sid: str,
                              student: dict = Depends(studentauth.current_student),
                              conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        try:
            return convo.complete(conn, sim, sid, student["id"])
        except convo.ConversationError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    # --- document submission surface --------------------------------------
    @app.post("/api/v1/sims/{slug}/submissions", status_code=201)
    def submit_doc(slug: str, req: SubmissionReq,
                   student: dict = Depends(studentauth.current_student),
                   conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        try:
            return subm.submit(conn, sim, student["id"], title=req.title, body=req.body,
                               application_id=req.application_id,
                               on_complete_event=req.on_complete_event,
                               review_delay_seconds=req.review_delay_seconds)
        except subm.SubmissionError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    @app.get("/api/v1/sims/{slug}/submissions")
    def list_docs(slug: str, student: dict = Depends(studentauth.current_student),
                  conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        return subm.list_submissions(conn, sim, student["id"])

    @app.get("/api/v1/sims/{slug}/submissions/{sid}")
    def get_doc(slug: str, sid: str, student: dict = Depends(studentauth.current_student),
                conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        try:
            return subm.get_submission(conn, sim, student["id"], sid)
        except subm.SubmissionError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    # --- group chat surface -----------------------------------------------
    @app.post("/api/v1/sims/{slug}/group-chats", status_code=201)
    def group_start(slug: str, req: GroupChatStartReq,
                    student: dict = Depends(studentauth.current_student),
                    conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        return gchat.start(conn, sim, student["id"], occasion=req.occasion,
                           participants=req.participants, beats=req.beats,
                           application_id=req.application_id,
                           beat_interval_seconds=req.beat_interval_seconds)

    @app.get("/api/v1/sims/{slug}/group-chats/{gid}")
    def group_get(slug: str, gid: str, student: dict = Depends(studentauth.current_student),
                  conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        try:
            return gchat.get(conn, sim, gid, student["id"])
        except gchat.GroupChatError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    @app.post("/api/v1/sims/{slug}/group-chats/{gid}/post")
    def group_post(slug: str, gid: str, req: GroupChatPostReq,
                   student: dict = Depends(studentauth.current_student),
                   conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        try:
            return gchat.post(conn, sim, gid, student["id"], req.text)
        except gchat.GroupChatError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    @app.post("/api/v1/sims/{slug}/group-chats/{gid}/complete")
    def group_complete(slug: str, gid: str,
                       student: dict = Depends(studentauth.current_student),
                       conn: sqlite3.Connection = Depends(get_conn)):
        sim = _student_sim(slug, student, conn)
        try:
            return gchat.complete(conn, sim, gid, student["id"])
        except gchat.GroupChatError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    # --- workflow runtime: UC view + advance ------------------------------
    @app.get("/api/v1/simulations/{sim_id}/applications")
    def uc_applications(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                        conn: sqlite3.Connection = Depends(get_conn)):
        return wfr.list_applications(conn, _owned_sim(sim_id, uc, conn))

    @app.post("/api/v1/simulations/{sim_id}/applications/{app_id}/advance")
    def uc_advance(sim_id: str, app_id: str, req: AdvanceReq,
                   uc: sqlite3.Row = Depends(current_uc),
                   conn: sqlite3.Connection = Depends(get_conn)):
        sim = _owned_sim(sim_id, uc, conn)
        try:
            app = wfr.get_application(conn, sim, app_id)
            return wfr.advance(conn, sim, app, req.event, req.context)
        except wfr.WorkflowRuntimeError as exc:
            raise HTTPException(exc.status, str(exc)) from exc

    # --- external-tool export (UC, stable schema_version contracts) -------
    @app.get("/api/v1/simulations/{sim_id}/export/applications")
    def export_applications(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                            conn: sqlite3.Connection = Depends(get_conn)):
        return export_svc.export_applications(conn, _owned_sim(sim_id, uc, conn))

    @app.get("/api/v1/simulations/{sim_id}/export/conversations")
    def export_conversations(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                             conn: sqlite3.Connection = Depends(get_conn)):
        return export_svc.export_conversations(conn, _owned_sim(sim_id, uc, conn))

    @app.get("/api/v1/simulations/{sim_id}/export/cohort")
    def export_cohort(sim_id: str, uc: sqlite3.Row = Depends(current_uc),
                      conn: sqlite3.Connection = Depends(get_conn)):
        return export_svc.export_cohort(conn, _owned_sim(sim_id, uc, conn))

    @app.get("/api/v1/simulations/{sim_id}/export/journey/{student_id}")
    def export_journey(sim_id: str, student_id: str, uc: sqlite3.Row = Depends(current_uc),
                       conn: sqlite3.Connection = Depends(get_conn)):
        return export_svc.export_journey(conn, _owned_sim(sim_id, uc, conn), student_id)

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
    app.mount("/portal", StaticFiles(directory=_STATIC / "portal", html=True), name="portal")

    @app.get("/")
    def root(conn: sqlite3.Connection = Depends(get_conn)):
        # Maintenance mode → public sees "coming soon"; admins use /preview/ or /admin/.
        if reg.maintenance_mode(conn):
            return FileResponse(_STATIC / "maintenance" / "index.html")
        return FileResponse(_STATIC / "landing" / "index.html")

    @app.get("/preview/")
    def preview():
        # Always serves the real landing — for the admin to test during maintenance.
        return FileResponse(_STATIC / "landing" / "index.html")

    @app.get("/api/v1/usage")
    def sim_usage_endpoint(uc: sqlite3.Row = Depends(current_uc),
                           conn: sqlite3.Connection = Depends(get_conn)):
        return sim_usage(conn, uc["id"])

    return app

