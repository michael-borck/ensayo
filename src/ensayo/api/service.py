"""Simulation lifecycle: create, (re)generate, publish — with git working clones.

The dashboard never touches git directly; this service does (docs/adr/0005). On
create/edit we write YAML to a per-simulation working clone, run the generator,
and commit. Publish pushes to GitHub when a remote + token are configured.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from ..config import load_company_config_from_text
from ..generator import generate
from .audit import audit
from .auth import hash_password


class ServiceError(Exception):
    """Raised on simulation create/generate/publish failures."""


def working_root() -> Path:
    raw = os.environ.get("WORKING_CLONES_DIR", "./.ensayo-data/sims")
    return Path(raw).expanduser()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- per-simulation locking (spec §3.2 working-clone management) -----------
# Mutating a working clone (write YAML → regenerate → commit → push) must be
# serialised per simulation. Concurrent edits to *different* sims run freely.

_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


def _lock_for(slug: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(slug, threading.Lock())


@contextmanager
def simulation_lock(slug: str):
    lock = _lock_for(slug)
    if not lock.acquire(timeout=120):
        raise ServiceError(f"timed out waiting for the lock on {slug!r}")
    try:
        yield
    finally:
        lock.release()


def _git(args: list[str], cwd: Path) -> None:
    cmd = ["git", "-c", "user.email=ensayo@localhost", "-c", "user.name=Ensayo",
           *args]
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ServiceError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d.pop("shared_password_hash", None)  # never expose
    d["has_unpublished_changes"] = bool(d.get("has_unpublished_changes"))
    d["auto_publish"] = bool(d.get("auto_publish"))
    if isinstance(d.get("config_cache"), str):
        try:
            d["config_cache"] = json.loads(d["config_cache"])
        except json.JSONDecodeError:
            d["config_cache"] = {}
    return d


_AUTH_MODES = ("shared_password", "individual_account", "email_only")


def create_simulation(
    conn: sqlite3.Connection, owner_uc_id: str, name: str, company_yaml: str, *,
    shared_password: str | None = None, auth_mode: str = "shared_password",
    workflow: str = "", with_llm: bool = False, build: bool = True, log=lambda m: None,
) -> dict:
    config = load_company_config_from_text(company_yaml)  # raises ConfigError if bad
    slug = config.slug

    if auth_mode not in _AUTH_MODES:
        raise ServiceError(f"auth_mode must be one of {_AUTH_MODES}")
    # Minors-safe bundle (spec §7.2/§7.3): shared password and no LLM-assist
    # unless the UC has acknowledged the override.
    minors = config.audience.value == "minors"
    overrides = set(config.audience_overrides)
    if minors and "individual_accounts" not in overrides:
        auth_mode = "shared_password"
    if with_llm and minors and "llm_assist" not in overrides:
        raise ServiceError(
            "LLM-assisted generation is off by default for minors audiences; "
            "acknowledge the 'llm_assist' override to enable it")

    if conn.execute("SELECT 1 FROM simulations WHERE slug = ?", (slug,)).fetchone():
        raise ServiceError(f"a simulation with slug {slug!r} already exists")

    clone = working_root() / slug
    base = f"/sims/{slug}/"
    with simulation_lock(slug):
        clone.mkdir(parents=True, exist_ok=True)
        (clone / "company.yaml").write_text(company_yaml, encoding="utf-8")
        if not (clone / ".git").exists():
            _git(["init", "-q"], clone)
        try:
            generate(clone / "company.yaml", clone, base=base, with_llm=with_llm,
                     build=build, log=log)
        except Exception as exc:  # surface generator/build errors to the API caller
            raise ServiceError(f"generation failed: {exc}") from exc
        _git(["add", "-A"], clone)
        _git(["commit", "-q", "-m", "Create simulation"], clone)

    sim_id = str(uuid.uuid4())
    now = _now()
    conn.execute(
        """INSERT INTO simulations
           (id, name, slug, type, audience, auth_mode, workflow, owner_uc_id,
            working_clone_path, site_url, status, shared_password_hash, config_cache,
            created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sim_id, name, slug, "single_company", config.audience.value, auth_mode, workflow,
         owner_uc_id, str(clone), base, "draft",
         hash_password(shared_password) if shared_password else "",
         json.dumps(config.model_dump(mode="json")), now, now),
    )
    conn.commit()
    audit("simulation.created", audience=config.audience.value, sim=slug,
          uc=owner_uc_id, auth_mode=auth_mode,
          overrides=[k for k in config.audience_overrides if k])
    return row_to_dict(conn.execute("SELECT * FROM simulations WHERE id = ?", (sim_id,)).fetchone())


def update_simulation(conn: sqlite3.Connection, sim: sqlite3.Row, company_yaml: str, *,
                      with_llm: bool = False, build: bool = True,
                      log=lambda m: None) -> dict:
    """Save edited content: rewrite YAML, regenerate, commit locally (spec §10.1).

    This is **Save** — it does not push. The simulation is marked as having
    unpublished changes (unless auto_publish is on, in which case it publishes)."""
    config = load_company_config_from_text(company_yaml)  # validate first
    clone = Path(sim["working_clone_path"])
    with simulation_lock(sim["slug"]):
        (clone / "company.yaml").write_text(company_yaml, encoding="utf-8")
        try:
            generate(clone / "company.yaml", clone, base=sim["site_url"],
                     with_llm=with_llm, build=build, log=log)
        except Exception as exc:
            raise ServiceError(f"generation failed: {exc}") from exc
        _git(["add", "-A"], clone)
        _git(["commit", "-q", "--allow-empty", "-m", "Save edit"], clone)
    conn.execute(
        "UPDATE simulations SET config_cache = ?, audience = ?, "
        "has_unpublished_changes = 1, updated_at = ? WHERE id = ?",
        (json.dumps(config.model_dump(mode="json")), config.audience.value, _now(),
         sim["id"]))
    conn.commit()
    sim = conn.execute("SELECT * FROM simulations WHERE id = ?", (sim["id"],)).fetchone()
    if sim["auto_publish"] and sim["repo_url"]:
        return {**row_to_dict(sim), "publish": publish(conn, sim)}
    return row_to_dict(sim)


def regenerate(conn: sqlite3.Connection, sim: sqlite3.Row, *, with_llm: bool = False,
               build: bool = True, log=lambda m: None) -> dict:
    clone = Path(sim["working_clone_path"])
    cfg_path = clone / "company.yaml"
    if not cfg_path.exists():
        raise ServiceError(f"working clone missing company.yaml: {clone}")
    with simulation_lock(sim["slug"]):
        try:
            generate(cfg_path, clone, base=sim["site_url"], with_llm=with_llm,
                     build=build, log=log)
        except Exception as exc:
            raise ServiceError(f"generation failed: {exc}") from exc
        _git(["add", "-A"], clone)
        _git(["commit", "-q", "--allow-empty", "-m", "Regenerate"], clone)
    conn.execute("UPDATE simulations SET has_unpublished_changes = 1, updated_at = ? "
                 "WHERE id = ?", (_now(), sim["id"]))
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM simulations WHERE id = ?",
                                    (sim["id"],)).fetchone())


# --- repo connection + publishing -----------------------------------------

def _parse_owner_repo(repo_url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from an https GitHub URL."""
    if "github.com/" not in repo_url:
        return None
    tail = repo_url.split("github.com/", 1)[1].removesuffix(".git").strip("/")
    parts = tail.split("/")
    return (parts[0], parts[1]) if len(parts) >= 2 else None


def _authed_remote(repo_url: str, token: str) -> str:
    if token and repo_url.startswith("https://"):
        return repo_url.replace("https://", f"https://x-access-token:{token}@")
    return repo_url  # local/file remotes (and tests) use the URL as-is


def connect_repo(conn: sqlite3.Connection, sim: sqlite3.Row, *,
                 repo_url: str = "", create_name: str = "") -> dict:
    """Attach a GitHub repo to a simulation. Optionally create it via the API."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if create_name:
        if not token:
            raise ServiceError("creating a repo requires GITHUB_TOKEN")
        try:
            r = httpx.post("https://api.github.com/user/repos",
                           headers={"Authorization": f"Bearer {token}",
                                    "Accept": "application/vnd.github+json"},
                           json={"name": create_name, "private": False,
                                 "auto_init": False}, timeout=30)
            r.raise_for_status()
            repo_url = r.json()["clone_url"]
        except httpx.HTTPError as exc:
            raise ServiceError(f"GitHub repo creation failed: {exc}") from exc
    if not repo_url:
        raise ServiceError("provide repo_url or create_name")

    clone = Path(sim["working_clone_path"])
    existing = subprocess.run(["git", "remote"], cwd=clone, capture_output=True, text=True)
    if "origin" in existing.stdout.split():
        _git(["remote", "set-url", "origin", repo_url], clone)
    else:
        _git(["remote", "add", "origin", repo_url], clone)
    conn.execute("UPDATE simulations SET repo_url = ?, updated_at = ? WHERE id = ?",
                 (repo_url, _now(), sim["id"]))
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM simulations WHERE id = ?",
                                    (sim["id"],)).fetchone())


def publish(conn: sqlite3.Connection, sim: sqlite3.Row) -> dict:
    """Publish to GitHub Pages: push content to main and the built site to gh-pages.

    Returns a status dict; a no-op (rather than an error) when no repo is connected
    so the dashboard can report it cleanly."""
    repo_url = sim["repo_url"]
    if not repo_url:
        return {"published": False, "reason": "no repo connected — connect a repo first"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if repo_url.startswith("https://") and not token:
        return {"published": False, "reason": "GITHUB_TOKEN not set for this instance"}

    clone = Path(sim["working_clone_path"])
    dist = clone / "dist"
    if not dist.exists():
        raise ServiceError("nothing built to publish — generate the site first")
    remote = _authed_remote(repo_url, token)

    with simulation_lock(sim["slug"]):
        # 1) content + history on main
        _git(["push", "-f", remote, "HEAD:main"], clone)
        # 2) built site as the gh-pages branch root (force; generated output)
        _publish_dist_to_gh_pages(dist, remote)

    _maybe_enable_pages(repo_url, token)
    conn.execute("UPDATE simulations SET status = 'active', has_unpublished_changes = 0, "
                 "last_published_at = ?, updated_at = ? WHERE id = ?",
                 (_now(), _now(), sim["id"]))
    conn.commit()
    pages_url = _pages_url(repo_url)
    return {"published": True, "pages_url": pages_url}


def _publish_dist_to_gh_pages(dist: Path, remote: str) -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        shutil.copytree(dist, tmpd, dirs_exist_ok=True)
        (tmpd / ".nojekyll").write_text("", encoding="utf-8")  # serve _astro/* dirs
        _git(["init", "-q"], tmpd)
        _git(["checkout", "-q", "-b", "gh-pages"], tmpd)
        _git(["add", "-A"], tmpd)
        _git(["commit", "-q", "-m", "Publish site"], tmpd)
        _git(["push", "-f", remote, "gh-pages"], tmpd)


def _pages_url(repo_url: str) -> str:
    pair = _parse_owner_repo(repo_url)
    return f"https://{pair[0]}.github.io/{pair[1]}/" if pair else ""


def _maybe_enable_pages(repo_url: str, token: str) -> None:
    """Best-effort: enable GitHub Pages from the gh-pages branch. Ignores failure."""
    pair = _parse_owner_repo(repo_url)
    if not pair or not token:
        return
    owner, repo = pair
    try:
        httpx.post(
            f"https://api.github.com/repos/{owner}/{repo}/pages",
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json"},
            json={"source": {"branch": "gh-pages", "path": "/"}}, timeout=30)
    except httpx.HTTPError:
        pass  # already enabled, or insufficient scope — not fatal


# --- booking service -------------------------------------------------------

_DEFAULT_HOURS = {"start": 9, "end": 17, "days": [0, 1, 2, 3, 4], "slot_minutes": 30}


def booking_enabled(sim: sqlite3.Row) -> bool:
    # config_cache holds model_dump() output, i.e. snake_case field names.
    try:
        cache = json.loads(sim["config_cache"])
        return bool(cache.get("platform", {}).get("booking_enabled"))
    except (json.JSONDecodeError, TypeError):
        return False


def _business_hours(sim: sqlite3.Row) -> dict:
    try:
        bh = json.loads(sim["config_cache"]).get("company", {}).get("business_hours")
    except (json.JSONDecodeError, TypeError):
        bh = None
    return {**_DEFAULT_HOURS, **bh} if isinstance(bh, dict) else dict(_DEFAULT_HOURS)


def availability(conn: sqlite3.Connection, sim: sqlite3.Row, employee_slug: str,
                 date_str: str) -> list[dict]:
    """Free appointment slots for an employee on a given YYYY-MM-DD date."""
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ServiceError("date must be YYYY-MM-DD") from exc
    hours = _business_hours(sim)
    if day.weekday() not in hours["days"]:
        return []
    booked = {r["slot_start"] for r in conn.execute(
        "SELECT slot_start FROM bookings WHERE simulation_id = ? AND employee_slug = ? "
        "AND status = 'confirmed'", (sim["id"], employee_slug))}
    step = timedelta(minutes=hours["slot_minutes"])
    slots: list[dict] = []
    cursor = datetime.combine(day, datetime.min.time()).replace(hour=hours["start"])
    end = datetime.combine(day, datetime.min.time()).replace(hour=hours["end"])
    while cursor < end:
        start_iso = cursor.isoformat()
        if start_iso not in booked:
            slots.append({"slot_start": start_iso, "slot_end": (cursor + step).isoformat()})
        cursor += step
    return slots


def create_booking(conn: sqlite3.Connection, sim: sqlite3.Row, employee_slug: str,
                   slot_start: str, student_name: str = "", student_email: str = "") -> dict:
    if not booking_enabled(sim):
        raise ServiceError("booking is not enabled for this simulation")
    taken = conn.execute(
        "SELECT 1 FROM bookings WHERE simulation_id = ? AND employee_slug = ? "
        "AND slot_start = ? AND status = 'confirmed'",
        (sim["id"], employee_slug, slot_start)).fetchone()
    if taken:
        raise ServiceError("that slot is already booked")
    try:
        start_dt = datetime.fromisoformat(slot_start)
    except ValueError as exc:
        raise ServiceError("slot_start must be ISO datetime") from exc
    step = timedelta(minutes=_business_hours(sim)["slot_minutes"])
    bid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO bookings (id, simulation_id, employee_slug, student_name, "
        "student_email, slot_start, slot_end, status, created_at) "
        "VALUES (?,?,?,?,?,?,?, 'confirmed', ?)",
        (bid, sim["id"], employee_slug, student_name, student_email, slot_start,
         (start_dt + step).isoformat(), _now()))
    conn.commit()
    return dict(conn.execute("SELECT * FROM bookings WHERE id = ?", (bid,)).fetchone())


def list_bookings(conn: sqlite3.Connection, sim: sqlite3.Row) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM bookings WHERE simulation_id = ? ORDER BY slot_start",
        (sim["id"],)).fetchall()
    return [dict(r) for r in rows]


def cancel_booking(conn: sqlite3.Connection, sim: sqlite3.Row, booking_id: str) -> dict:
    row = conn.execute("SELECT * FROM bookings WHERE id = ? AND simulation_id = ?",
                       (booking_id, sim["id"])).fetchone()
    if row is None:
        raise ServiceError("booking not found")
    conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
    conn.commit()
    return {"cancelled": True, "id": booking_id}


# --- visibility rules (server-enforced) ------------------------------------

def add_visibility_rule(conn: sqlite3.Connection, sim: sqlite3.Row, *, target_type: str,
                        target_id: str, action: str = "hide", trigger_type: str = "always",
                        trigger_value: str = "", unit_code: str = "") -> dict:
    if target_type not in ("document", "employee", "page", "chatbot"):
        raise ServiceError("target_type must be document|employee|page|chatbot")
    if action not in ("show", "hide"):
        raise ServiceError("action must be show|hide")
    if trigger_type not in ("always", "datetime"):
        raise ServiceError("trigger_type must be always|datetime")
    rid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO visibility_rules (id, simulation_id, unit_code, target_type, "
        "target_id, action, trigger_type, trigger_value, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (rid, sim["id"], unit_code, target_type, target_id, action, trigger_type,
         trigger_value, _now()))
    conn.commit()
    return dict(conn.execute("SELECT * FROM visibility_rules WHERE id = ?", (rid,)).fetchone())


def list_visibility_rules(conn: sqlite3.Connection, sim: sqlite3.Row) -> list[dict]:
    rows = conn.execute("SELECT * FROM visibility_rules WHERE simulation_id = ? "
                        "ORDER BY created_at", (sim["id"],)).fetchall()
    return [dict(r) for r in rows]


def delete_visibility_rule(conn: sqlite3.Connection, sim: sqlite3.Row, rule_id: str) -> dict:
    cur = conn.execute("DELETE FROM visibility_rules WHERE id = ? AND simulation_id = ?",
                       (rule_id, sim["id"]))
    conn.commit()
    if cur.rowcount == 0:
        raise ServiceError("rule not found")
    return {"deleted": True, "id": rule_id}


def evaluate_visibility(conn: sqlite3.Connection, sim: sqlite3.Row, *, unit_code: str = "",
                        now: datetime | None = None) -> dict:
    """Compute which targets are hidden *right now* (server-enforced gating).

    A datetime rule is active once its trigger time has passed. Returns the list
    of currently-hidden targets so a static site can enforce gating via the API."""
    now = now or datetime.now(timezone.utc)
    rows = conn.execute(
        "SELECT * FROM visibility_rules WHERE simulation_id = ? AND (unit_code = '' OR unit_code = ?)",
        (sim["id"], unit_code)).fetchall()
    hidden: list[dict] = []
    for r in rows:
        active = True
        if r["trigger_type"] == "datetime" and r["trigger_value"]:
            try:
                active = now >= datetime.fromisoformat(r["trigger_value"])
            except ValueError:
                active = False
        # 'hide' active → hidden; 'show' active → explicitly shown (overrides).
        if r["action"] == "hide" and active:
            hidden.append({"target_type": r["target_type"], "target_id": r["target_id"]})
    return {"unit_code": unit_code, "hidden": hidden}
