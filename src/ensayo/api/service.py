"""Simulation lifecycle: create, (re)generate, publish — with git working clones.

The dashboard never touches git directly; this service does (docs/adr/0005). On
create/edit we write YAML to a per-simulation working clone, run the generator,
and commit. Publish pushes to GitHub when a remote + token are configured.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config import load_company_config_from_text
from ..generator import generate
from .auth import hash_password


class ServiceError(Exception):
    """Raised on simulation create/generate/publish failures."""


def working_root() -> Path:
    raw = os.environ.get("WORKING_CLONES_DIR", "./.ensayo-data/sims")
    return Path(raw).expanduser()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def create_simulation(
    conn: sqlite3.Connection, owner_uc_id: str, name: str, company_yaml: str, *,
    shared_password: str | None = None, with_llm: bool = False, build: bool = True,
    log=lambda m: None,
) -> dict:
    config = load_company_config_from_text(company_yaml)  # raises ConfigError if bad
    slug = config.slug

    if conn.execute("SELECT 1 FROM simulations WHERE slug = ?", (slug,)).fetchone():
        raise ServiceError(f"a simulation with slug {slug!r} already exists")

    clone = working_root() / slug
    clone.mkdir(parents=True, exist_ok=True)
    (clone / "company.yaml").write_text(company_yaml, encoding="utf-8")

    if not (clone / ".git").exists():
        _git(["init", "-q"], clone)

    base = f"/sims/{slug}/"
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
           (id, name, slug, type, audience, owner_uc_id, working_clone_path,
            site_url, status, shared_password_hash, config_cache, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sim_id, name, slug, "single_company", config.audience.value, owner_uc_id,
         str(clone), base, "draft",
         hash_password(shared_password) if shared_password else "",
         json.dumps(config.model_dump(mode="json")), now, now),
    )
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM simulations WHERE id = ?", (sim_id,)).fetchone())


def regenerate(conn: sqlite3.Connection, sim: sqlite3.Row, *, with_llm: bool = False,
               build: bool = True, log=lambda m: None) -> dict:
    clone = Path(sim["working_clone_path"])
    cfg_path = clone / "company.yaml"
    if not cfg_path.exists():
        raise ServiceError(f"working clone missing company.yaml: {clone}")
    try:
        generate(cfg_path, clone, base=sim["site_url"], with_llm=with_llm,
                 build=build, log=log)
    except Exception as exc:
        raise ServiceError(f"generation failed: {exc}") from exc
    _git(["add", "-A"], clone)
    # allow-empty so a no-op regenerate still succeeds
    _git(["commit", "-q", "--allow-empty", "-m", "Regenerate"], clone)
    conn.execute("UPDATE simulations SET updated_at = ? WHERE id = ?", (_now(), sim["id"]))
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM simulations WHERE id = ?",
                                    (sim["id"],)).fetchone())


def publish(conn: sqlite3.Connection, sim: sqlite3.Row) -> dict:
    """Push the working clone to its GitHub remote, if configured.

    Returns a status dict. Without repo_url + GITHUB_TOKEN this is a no-op that
    reports the situation rather than failing (real push lands when a UC connects
    a repo in a later increment)."""
    clone = Path(sim["working_clone_path"])
    repo_url = sim["repo_url"]
    token = os.environ.get("GITHUB_TOKEN", "")
    if not repo_url or not token:
        return {"published": False,
                "reason": "no repo_url and/or GITHUB_TOKEN configured for this simulation"}
    remote = repo_url.replace("https://", f"https://x-access-token:{token}@")
    _git(["push", remote, "HEAD:gh-pages", "-f"], clone)
    conn.execute("UPDATE simulations SET status = 'active', has_unpublished_changes = 0, "
                 "updated_at = ? WHERE id = ?", (_now(), sim["id"]))
    conn.commit()
    return {"published": True}
