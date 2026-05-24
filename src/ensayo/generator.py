"""Generation pipeline: ``company.yaml`` → content → static ``dist/``.

The generator runs on the VPS (or a power user's machine), never in CI
(spec §3.4). It copies the chosen Astro theme into an isolated build workspace,
injects the simulation's content as Astro content collections, runs the Astro
build, and captures the static output.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import load_company_config
from .content import write_repo_content, write_theme_data
from .enrich import enrich_config
from .llm import get_provider
from .models import CompanyConfig
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
    shutil.copyfile(Path(config_path), output_dir / "company.yaml")

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


def _build_site(
    config: CompanyConfig, theme_dir: Path, output_dir: Path,
    base: str | None, log: Logger
) -> Path:
    if shutil.which("npm") is None:
        raise GenerationError(
            "npm not found. Install Node 20+ to build themes, or use --no-build."
        )

    build_root = output_dir / ".ensayo-build"
    work = build_root / config.slug
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    log(f"Copying theme {theme_dir.name} → build workspace")
    shutil.copytree(theme_dir, work, ignore=_THEME_IGNORE, dirs_exist_ok=True)

    # Reuse the theme's vendored node_modules by symlinking (copying would
    # dereference the .bin/* symlinks and break Astro's CLI shim).
    vendored = theme_dir / "node_modules"
    link = work / "node_modules"
    if vendored.exists() and not link.exists():
        log("Linking theme's vendored node_modules")
        link.symlink_to(vendored.resolve(), target_is_directory=True)

    write_theme_data(config, work / "src")
    _install_shared_assets(work)

    if not (work / "node_modules").exists():
        _run(["npm", _install_cmd(work), "--no-audit", "--no-fund"], work, log,
             "installing theme dependencies (npm)")

    build_env = dict(os.environ)
    if base:
        build_env["ENSAYO_BASE"] = base if base.endswith("/") else base + "/"
        log(f"Building with base path: {build_env['ENSAYO_BASE']}")
    _run(["npm", "run", "build"], work, log, "building site (astro)", env=build_env)

    built_dist = work / "dist"
    if not built_dist.exists():
        raise GenerationError(f"Astro build produced no dist/ in {work}")

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
