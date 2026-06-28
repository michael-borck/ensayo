"""Generation pipeline: ``company.yaml`` → content → static ``dist/``.

The generator runs on the VPS (or a power user's machine), never in CI
(spec §3.4). It copies the chosen Astro theme into an isolated build workspace,
injects the simulation's content as Astro content collections, runs the Astro
build, and captures the static output.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import dump_config_yaml, load_company_config, load_simulation_config
from .content import write_repo_content, write_theme_data
from .enrich import enrich_config
from .llm import get_provider
from .models import CompanyConfig, SimulationConfig
from .themes import default_themes_dir, resolve_theme

# Directories never copied from a theme into the build workspace.
_THEME_IGNORE = shutil.ignore_patterns("node_modules", "dist", ".astro", ".git")

Logger = Callable[[str], None]


def _noop(_: str) -> None:  # pragma: no cover
    pass


class GenerationError(Exception):
    """Raised when generation fails (theme build error, missing tooling, etc.)."""


@dataclass
class GenerationResult:
    config: CompanyConfig
    output_dir: Path
    dist_dir: Path | None
    built: bool
    content_manifest: dict = field(default_factory=dict)


@dataclass
class MultisiteResult:
    config: SimulationConfig
    output_dir: Path
    dist_dir: Path | None
    built: bool
    company_results: list = field(default_factory=list)


def generate(
    config_path: str | Path,
    output_dir: str | Path,
    *,
    theme: str | None = None,
    themes_dir: str | Path | None = None,
    base: str | None = None,
    with_llm: bool = False,
    force_llm: bool = False,
    build: bool = True,
    log: Logger = _noop,
) -> GenerationResult:
    """Generate a simulation site from *config_path* into *output_dir*.

    *base* sets the site's base path (e.g. ``/sims/acme/``) for path-based Caddy
    routing and multi-site subpaths. Defaults to ``/``.

    *with_llm* runs bulk content generation (spec §10.6) to fill in missing
    backstories, opinions, perspectives, the scenario, and document bodies before
    building. *force_llm* regenerates even content that's already present.
    """
    config = load_company_config(config_path)
    output_dir = Path(output_dir).resolve()
    themes_dir = Path(themes_dir).resolve() if themes_dir else default_themes_dir()
    theme_name = theme or config.theme

    log(f"Loaded simulation: {config.company.name} ({config.slug})")
    log(f"Theme: {theme_name}  |  audience: {config.audience.value}  |  "
        f"chatbot: {config.chatbot_mode.value}")

    if with_llm:
        _run_enrichment(config, force_llm, log)

    theme_dir = resolve_theme(theme_name, themes_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    # Keep a copy of the config in the output (skip if it's already that file,
    # e.g. when regenerating in place from a working clone).
    src = Path(config_path).resolve()
    dst = (output_dir / "company.yaml").resolve()
    if src != dst:
        shutil.copyfile(src, dst)

    manifest = write_repo_content(config, output_dir)
    log(f"Wrote canonical content: {manifest['employees']} employees, "
        f"{manifest['documents']} documents → {output_dir / 'content'}")

    if not build:
        log("Skipping Astro build (--no-build). Theme data not injected.")
        return GenerationResult(config, output_dir, None, built=False,
                                content_manifest=manifest)

    dist_dir = _build_site(config, theme_dir, output_dir, base, log)
    return GenerationResult(config, output_dir, dist_dir, built=True,
                            content_manifest=manifest)


def _run_enrichment(config: CompanyConfig, force: bool, log: Logger) -> None:
    from .enrich import estimate
    from .models import Audience

    provider, spec = get_provider(config)
    if config.audience is Audience.minors and spec.provider != "stub":
        log("⚠ audience=minors: LLM generation is off by default for minors "
            "audiences — proceeding because it was explicitly requested.")

    est = estimate(config, force=force)
    if est["items"] == 0:
        log("LLM generation: nothing to generate (content already present; use "
            "--force-llm to regenerate).")
        return
    log(f"LLM generation via '{spec.provider}'"
        f"{(' (' + spec.model + ')') if spec.model and spec.provider != 'stub' else ''}: "
        f"{est['items']} items, ~{est['input_tokens']:,} in / "
        f"~{est['output_tokens']:,} out tokens (estimate).")

    def progress(item, phase):
        if phase == "done":
            mark = "✓" if item.status == "generated" else "✗"
            log(f"  {mark} {item.label}" + (f" — {item.error}" if item.error else ""))

    result = enrich_config(config, provider, spec, force=force, on_progress=progress)
    tok = ""
    if result.input_tokens or result.output_tokens:
        tok = f"  ({result.input_tokens:,} in / {result.output_tokens:,} out tokens used)"
    log(f"LLM generation done: {result.generated} generated, {result.failed} failed.{tok}")


def _prepare_workspace(theme_dir: Path, work: Path, log: Logger) -> None:
    """Copy a theme into an isolated build workspace + reuse its vendored deps."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    log(f"Copying theme {theme_dir.name} → build workspace")
    shutil.copytree(theme_dir, work, ignore=_THEME_IGNORE, dirs_exist_ok=True)
    # Symlink vendored node_modules (copying dereferences .bin/* symlinks).
    vendored = theme_dir / "node_modules"
    link = work / "node_modules"
    if vendored.exists() and not link.exists():
        link.symlink_to(vendored.resolve(), target_is_directory=True)
    _install_shared_assets(work)


def _compile(work: Path, base: str | None, log: Logger) -> Path:
    """Run the Astro build in *work* and return its dist/ path."""
    if shutil.which("npm") is None:
        raise GenerationError(
            "npm not found. Install Node 20+ to build themes, or use --no-build.")
    if not (work / "node_modules").exists():
        _run(["npm", _install_cmd(work), "--no-audit", "--no-fund"], work, log,
             "installing theme dependencies (npm)")
    build_env = dict(os.environ)
    if base:
        build_env["ENSAYO_BASE"] = base if base.endswith("/") else base + "/"
        log(f"Building with base path: {build_env['ENSAYO_BASE']}")
    _run(["npm", "run", "build"], work, log, "building site (astro)", env=build_env)
    dist = work / "dist"
    if not dist.exists():
        raise GenerationError(f"Astro build produced no dist/ in {work}")
    return dist


def _build_site(
    config: CompanyConfig, theme_dir: Path, output_dir: Path,
    base: str | None, log: Logger
) -> Path:
    work = output_dir / ".ensayo-build" / config.slug
    _prepare_workspace(theme_dir, work, log)
    write_theme_data(config, work / "src")
    built_dist = _compile(work, base, log)

    final_dist = output_dir / "dist"
    if final_dist.exists():
        shutil.rmtree(final_dist)
    shutil.copytree(built_dist, final_dist)
    log(f"Built static site → {final_dist}")
    return final_dist


def _install_cmd(work: Path) -> str:
    return "ci" if (work / "package-lock.json").exists() else "install"


def _install_shared_assets(work: Path) -> None:
    """Copy shared client assets (keyword chatbot, etc.) into the theme's public/."""
    shared = Path(__file__).resolve().parent / "shared"
    public = work / "public" / "ensayo"
    public.mkdir(parents=True, exist_ok=True)
    for asset in shared.glob("*.js"):
        shutil.copyfile(asset, public / asset.name)


def _run(cmd: list[str], cwd: Path, log: Logger, what: str,
         env: dict | None = None) -> None:
    log(f"→ {what}: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise GenerationError(
            f"{what} failed (exit {proc.returncode}).\n"
            f"--- stdout ---\n{proc.stdout[-2000:]}\n"
            f"--- stderr ---\n{proc.stderr[-2000:]}"
        )


# --- multi-site generation (Phase 8) ---------------------------------------

def generate_multisite(
    config_path: str | Path, output_dir: str | Path, *,
    base: str = "/", themes_dir: str | Path | None = None,
    with_llm: bool = False, force_llm: bool = False, build: bool = True,
    log: Logger = _noop,
) -> MultisiteResult:
    """Generate a multi-site simulation: a portal + N company sites in one repo.

    Each company is built at the subpath ``{base}{company_slug}/``; a portal index
    is written at the repo root linking to them (spec §12)."""
    sim = load_simulation_config(config_path)
    output_dir = Path(output_dir).resolve()
    themes_dir = Path(themes_dir).resolve() if themes_dir else default_themes_dir()
    base = base if base.endswith("/") else base + "/"

    log(f"Loaded multi-site simulation: {sim.name} ({sim.slug}) — "
        f"{len(sim.companies)} companies")
    output_dir.mkdir(parents=True, exist_ok=True)
    _src, _dst = Path(config_path), output_dir / "simulation.yaml"
    if _src.resolve() != _dst.resolve():  # dashboard already wrote it in-place
        shutil.copyfile(_src, _dst)

    dist = output_dir / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)

    results: list[GenerationResult] = []
    for company in sim.companies:
        company_base = f"{base}{company.slug}/"
        company_dir = output_dir / "companies" / company.slug
        company_dir.mkdir(parents=True, exist_ok=True)
        (company_dir / "company.yaml").write_text(dump_config_yaml(company), encoding="utf-8")
        log(f"— {company.company.name} → {company_base}")
        res = generate(company_dir / "company.yaml", company_dir, base=company_base,
                       themes_dir=themes_dir, with_llm=with_llm, force_llm=force_llm,
                       build=build, log=lambda m: log("  " + m))
        if res.built and res.dist_dir:
            shutil.copytree(res.dist_dir, dist / company.slug)
        results.append(res)

    if build:
        # Portal hub at the root, job-board "directory" at /jobs/.
        portal_data = {"portal.json": json.dumps(_portal_payload(sim, base))}
        portal_dist = _build_aux_theme("portal-clean", output_dir, themes_dir,
                                       portal_data, base, log)
        shutil.copytree(portal_dist, dist, dirs_exist_ok=True)

        jobs_data = {"jobs.json": json.dumps(
            {"jobs": sim.aggregate_jobs(), "base": base, "name": sim.name})}
        dir_dist = _build_aux_theme("directory", output_dir, themes_dir,
                                    jobs_data, f"{base}jobs/", log)
        jobs_target = dist / "jobs"
        if jobs_target.exists():
            shutil.rmtree(jobs_target)
        shutil.copytree(dir_dist, jobs_target)
    else:
        (dist / "index.html").write_text(_portal_index_html(sim, base), encoding="utf-8")

    log(f"Portal + {len(sim.companies)} companies → {dist}")
    return MultisiteResult(sim, output_dir, dist if build else None, build, results)


def _portal_payload(sim: SimulationConfig, base: str) -> dict:
    return {
        "name": sim.name,
        "title": sim.portal.title or sim.name,
        "tagline": sim.portal.tagline,
        "description": sim.portal.description,
        "portalAppUrl": "/portal/",   # the interactive student portal SPA on the VPS
        "jobsUrl": f"{base}jobs/",
        "jobsCount": len(sim.aggregate_jobs()),
        "companies": [{"name": c.company.name, "slug": c.slug,
                       "tagline": c.company.tagline or c.company.industry,
                       "url": f"{base}{c.slug}/"} for c in sim.companies],
    }


def _build_aux_theme(theme_name: str, output_dir: Path, themes_dir: Path,
                     data_files: dict[str, str], base: str, log: Logger) -> Path:
    """Build a non-company theme (portal/directory) with injected JSON data."""
    theme_dir = resolve_theme(theme_name, themes_dir)
    work = output_dir / ".ensayo-build" / f"_{theme_name}"
    _prepare_workspace(theme_dir, work, log)
    data_dir = work / "src" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for rel, content in data_files.items():
        (data_dir / rel).write_text(content, encoding="utf-8")
    log(f"— {theme_name} → {base}")
    return _compile(work, base, log)


def _portal_index_html(sim: SimulationConfig, base: str) -> str:
    title = sim.portal.title or sim.name
    tagline = sim.portal.tagline or ""
    cards = "\n".join(
        f'      <a class="card" href="{base}{c.slug}/">'
        f'<strong>{c.company.name} →</strong>'
        f'<span>{c.company.tagline or c.company.industry}</span></a>'
        for c in sim.companies
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{ margin:0; min-height:100vh; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      background: radial-gradient(900px 500px at 70% -10%, #243, #0e1118) fixed; color:#e7ecf3; }}
    main {{ max-width:760px; margin:0 auto; padding:3rem 1.5rem; }}
    h1 {{ font-size:2.6rem; margin:0 0 0.3rem; }}
    .tag {{ color:#00d4aa; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; font-size:0.8rem; }}
    p {{ color:#97a3b6; line-height:1.6; }}
    .grid {{ display:grid; gap:0.8rem; margin-top:1.5rem; }}
    .card {{ display:flex; flex-direction:column; gap:0.25rem; padding:1.1rem 1.3rem; border:1px solid #2a3344;
      border-radius:14px; background:#161b26; color:inherit; text-decoration:none; }}
    .card:hover {{ border-color:#00d4aa; }}
    .card strong {{ font-size:1.1rem; }}
    .card span {{ color:#97a3b6; }}
  </style>
</head>
<body>
  <main>
    <p class="tag">{sim.name}</p>
    <h1>{title}</h1>
    <p>{tagline}</p>
    <div class="grid">
{cards}
    </div>
  </main>
</body>
</html>
"""
