"""``ensayo`` command-line interface."""

from __future__ import annotations
try:  # Load .env from CWD if present (override=False → real env wins).
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv optional; env can be supplied directly
    pass

from pathlib import Path

import click

from . import __version__
from .config import (ConfigError, dump_config_yaml, is_multisite,
                     load_company_config, load_simulation_config)
from .enrich import enrich_config, estimate
from .generator import GenerationError, generate, generate_multisite
from .llm import get_provider
from .themes import ThemeError, default_themes_dir, list_themes
from .workflow import WorkflowError, list_workflows, load_workflow
from .workflow import run as run_workflow

_THEMES_OPT = click.option(
    "--themes-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory containing theme packages (default: bundled themes/).",
)


@click.group()
@click.version_option(__version__, prog_name="ensayo")
def main() -> None:
    """Ensayo — generate workplace teaching simulations from configuration."""


@main.command(name="generate")
@click.option("--config", "-c", required=True, type=click.Path(path_type=Path),
              help="Path to company.yaml.")
@click.option("--output", "-o", default="./dist-out", type=click.Path(path_type=Path),
              help="Output directory for the generated simulation.")
@click.option("--theme", default=None, help="Override the theme named in the config.")
@_THEMES_OPT
@click.option("--base", default=None,
              help="Base path for the site, e.g. /sims/acme/ (default: /).")
@click.option("--with-llm", is_flag=True, default=False,
              help="Bulk-generate missing content (backstories, docs, scenario) first.")
@click.option("--force-llm", is_flag=True, default=False,
              help="With --with-llm, regenerate content even if already present.")
@click.option("--no-build", is_flag=True, default=False,
              help="Write content only; skip the Astro build (no Node required).")
def generate_cmd(config: Path, output: Path, theme: str | None,
                 themes_dir: Path | None, base: str | None,
                 with_llm: bool, force_llm: bool, no_build: bool) -> None:
    """Generate a static simulation site (single-company or multi-site, auto-detected)."""
    log = lambda m: click.echo(click.style("  " + m, dim=True))
    multisite = is_multisite(config)
    try:
        if multisite:
            result = generate_multisite(
                config, output, themes_dir=themes_dir, base=base or "/",
                with_llm=with_llm or force_llm, force_llm=force_llm,
                build=not no_build, log=log)
        else:
            result = generate(
                config, output, theme=theme, themes_dir=themes_dir, base=base,
                with_llm=with_llm or force_llm, force_llm=force_llm,
                build=not no_build, log=log)
    except (ConfigError, ThemeError, GenerationError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.secho("✓ Generation complete" + (" (multi-site)" if multisite else ""),
                fg="green", bold=True)
    if result.built and result.dist_dir:
        click.echo(f"  Static site: {result.dist_dir}")
        click.echo(f"  Preview:     python3 -m http.server -d {result.dist_dir} 8000")
    else:
        click.echo(f"  Content written to {result.output_dir} (build skipped)")


@main.command()
@click.option("--config", "-c", required=True, type=click.Path(path_type=Path))
def validate(config: Path) -> None:
    """Validate a company.yaml or simulation.yaml (multi-site auto-detected)."""
    try:
        if is_multisite(config):
            sim = load_simulation_config(config)
            click.secho("✓ Config is valid (multi-site)", fg="green", bold=True)
            click.echo(f"  Simulation: {sim.name} ({sim.slug})")
            click.echo(f"  Audience:   {sim.audience.value}")
            click.echo(f"  Workflow:   {sim.workflow or '—'}")
            click.echo(f"  Companies:  {len(sim.companies)}")
            for c in sim.companies:
                click.echo(f"    - {c.company.name} ({c.slug}, theme: {c.theme})")
            return
        cfg = load_company_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc
    click.secho("✓ Config is valid", fg="green", bold=True)
    click.echo(f"  Company:   {cfg.company.name} ({cfg.slug})")
    click.echo(f"  Theme:     {cfg.theme}")
    click.echo(f"  Audience:  {cfg.audience.value}")
    click.echo(f"  Chatbot:   {cfg.chatbot_mode.value}")
    click.echo(f"  Employees: {len(cfg.employees)}")
    click.echo(f"  Documents: {len(cfg.documents)}")


@main.command()
@click.option("--config", "-c", required=True, type=click.Path(path_type=Path))
@click.option("--output", "-o", default=None, type=click.Path(path_type=Path),
              help="Write enriched YAML here (default: print to stdout).")
@click.option("--force", is_flag=True, default=False,
              help="Regenerate content even if already present.")
@click.option("--estimate-only", is_flag=True, default=False,
              help="Show the token-count estimate and exit without generating.")
def enrich(config: Path, output: Path | None, force: bool, estimate_only: bool) -> None:
    """LLM-fill missing content (backstories, docs, scenario) into a company.yaml."""
    try:
        cfg = load_company_config(config)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    provider, spec = get_provider(cfg)
    est = estimate(cfg, force=force)
    click.secho(
        f"Provider: {spec.provider}"
        f"{(' (' + spec.model + ')') if spec.model and spec.provider != 'stub' else ''}",
        bold=True)
    click.echo(f"Items to generate: {est['items']}  "
               f"({', '.join(f'{k}×{v}' for k, v in est['by_kind'].items()) or '—'})")
    click.echo(f"Estimated tokens: ~{est['input_tokens']:,} in / ~{est['output_tokens']:,} out "
               "(check your provider's pricing for cost).")
    if estimate_only or est["items"] == 0:
        if est["items"] == 0:
            click.echo("Nothing to generate. Use --force to regenerate existing content.")
        return

    def progress(item, phase):
        if phase == "done":
            mark = click.style("✓", fg="green") if item.status == "generated" \
                else click.style("✗", fg="red")
            click.echo(f"  {mark} {item.label}" + (f" — {item.error}" if item.error else ""))

    result = enrich_config(cfg, provider, spec, force=force, on_progress=progress)
    click.secho(f"✓ {result.generated} generated, {result.failed} failed", fg="green", bold=True)

    yaml_text = dump_config_yaml(result.config)
    if output:
        output.write_text(yaml_text, encoding="utf-8")
        click.echo(f"  Enriched config written to {output}")
    else:
        click.echo("\n" + yaml_text)


@main.command(name="list")
@_THEMES_OPT
def list_cmd(themes_dir: Path | None) -> None:
    """List available themes and what they support."""
    tdir = themes_dir or default_themes_dir()
    themes = list_themes(tdir)
    if not themes:
        click.echo(f"No themes found in {tdir}")
        return
    click.secho(f"Themes in {tdir}:", bold=True)
    for m in themes:
        modes = ", ".join(m.supports.get("chatbot_modes", [])) or "—"
        click.echo(f"  • {click.style(m.name, fg='cyan')} — {m.description}")
        click.echo(f"      chatbot modes: {modes}")


@main.command()
@click.option("--output", "-o", default="./gallery", type=click.Path(path_type=Path),
              help="Output directory for the theme gallery.")
@click.option("--config", "-c", default=None, type=click.Path(path_type=Path),
              help="Company config to render (default: bundled NexusPoint example).")
@_THEMES_OPT
@click.option("--no-build", is_flag=True, default=False, help="Content only; skip Astro builds.")
def gallery(output: Path, config: Path | None, themes_dir: Path | None,
            no_build: bool) -> None:
    """Render one demo company across every company theme for visual comparison."""
    tdir = themes_dir or default_themes_dir()
    cfg = config or (default_themes_dir().parent / "examples" / "nexuspoint" / "company.yaml")
    if not Path(cfg).exists():
        raise click.ClickException(f"demo config not found: {cfg}")
    names = [m.name for m in list_themes(tdir) if "company" in m.content_props]
    if not names:
        raise click.ClickException("no company themes found")
    output.mkdir(parents=True, exist_ok=True)
    log = lambda m: click.echo(click.style("  " + m, dim=True))
    built = []
    for name in names:
        click.secho(f"→ {name}", fg="cyan")
        try:
            res = generate(cfg, output / ".work" / name, theme=name, themes_dir=tdir,
                           base=f"/{name}/", build=not no_build, log=log)
        except (ConfigError, ThemeError, GenerationError) as exc:
            raise click.ClickException(str(exc)) from exc
        if res.built and res.dist_dir:
            import shutil
            site = output / name
            if site.exists():
                shutil.rmtree(site)
            shutil.copytree(res.dist_dir, site)
        built.append(name)
    links = "\n".join(f'    <li><a href="./{n}/">{n}</a></li>' for n in built)
    (output / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><title>Ensayo theme gallery</title>"
        f"<h1>Ensayo theme gallery</h1><ul>\n{links}\n</ul>", encoding="utf-8")
    click.secho(f"✓ Gallery of {len(built)} themes → {output}", fg="green", bold=True)
    if not no_build:
        click.echo(f"  Preview: python3 -m http.server -d {output} 8000")


@main.command()
@click.option("--output", "-o", default="./company.yaml", type=click.Path(path_type=Path))
@click.option("--name", default="Acme Corp", help="Company name to seed the file with.")
def init(output: Path, name: str) -> None:
    """Write a starter company.yaml to edit."""
    if output.exists():
        raise click.ClickException(f"{output} already exists — refusing to overwrite.")
    output.write_text(_STARTER.replace("{{NAME}}", name), encoding="utf-8")
    click.secho(f"✓ Wrote starter config to {output}", fg="green")
    click.echo("  Edit it, then run: ensayo generate -c " + str(output))


@main.command()
@click.option("--host", default="127.0.0.1", help="Bind host.")
@click.option("--port", default=8000, type=int, help="Bind port.")
@click.option("--reload", is_flag=True, default=False, help="Auto-reload (dev).")
def serve(host: str, port: int, reload: bool) -> None:
    """Run the Ensayo API + dashboard (FastAPI/uvicorn)."""
    import uvicorn

    click.secho(f"Ensayo dashboard → http://{host}:{port}/admin/", fg="cyan", bold=True)
    uvicorn.run("ensayo.api.app:create_app", factory=True,
                host=host, port=port, reload=reload)


@main.group()
def admin() -> None:
    """Instance administration (account management)."""


@admin.command(name="create-uc")
@click.option("--email", "-e", required=True, help="UC email (login).")
@click.option("--password", "-p", default=None, help="Password (prompted if omitted).")
@click.option("--name", default="", help="Display name.")
@click.option("--admin", "is_admin", is_flag=True, default=False,
              help="Create an instance admin (full access) instead of a regular UC.")
def create_uc(email: str, password: str | None, name: str, is_admin: bool) -> None:
    """Create a UC (or instance-admin) account in the database."""
    from .api.auth import create_uc as _create_uc
    from .api.db import init_db

    if not password:
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
    conn = init_db()
    try:
        uc = _create_uc(conn, email, password, display_name=name,
                        role="instance_admin" if is_admin else "uc")
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()
    click.secho(f"✓ Created {uc['role']} account: {uc['email']}", fg="green")
    click.echo("  Log in at /admin/ after starting the server with: ensayo serve")

@admin.command(name="send-test-email")
@click.option("--to", "to_email", required=True, help="Recipient address.")
def send_test_email(to_email: str) -> None:
    """Send a test email to verify the configured provider delivers."""
    from .api import email as email_svc

    prov = email_svc.provider()
    if not email_svc.configured():
        click.secho(f"EMAIL_PROVIDER={prov or 'console'} — no real provider configured. "
                    f"Set EMAIL_PROVIDER (smtp|resend) and its credentials in .env.",
                    fg="yellow")
        return
    ok = email_svc.send_email(to_email, "Ensayo test email",
                              "If you can read this, Ensayo's email is wired correctly.")
    if ok:
        click.secho(f"\u2713 Sent test email to {to_email} via '{prov}'.", fg="green")
    else:
        click.secho(f"\u2717 Send failed via '{prov}' — check credentials/env.", fg="red")
        raise SystemExit(1)


@main.group(name="workflow")
def workflow_group() -> None:
    """Inspect and dry-run declarative workflows (Phase 7)."""


@workflow_group.command(name="list")
def workflow_list() -> None:
    """List bundled workflow templates."""
    names = list_workflows()
    if not names:
        click.echo("No workflows found.")
        return
    for n in names:
        wf = load_workflow(n)
        click.echo(f"  • {click.style(n, fg='cyan')} — {wf.description} "
                   f"({len(wf.stages)} stages)")


@workflow_group.command(name="validate")
@click.option("--workflow", "-w", "wf", required=True, help="Workflow name or path.")
def workflow_validate(wf: str) -> None:
    """Validate a workflow YAML."""
    try:
        w = load_workflow(wf)
    except WorkflowError as exc:
        raise click.ClickException(str(exc)) from exc
    click.secho(f"✓ {w.name} is valid", fg="green", bold=True)
    for s in w.stages:
        surf = ", ".join(s.surfaces) or "—"
        term = " [terminal]" if s.terminal else ""
        click.echo(f"  {s.id}{term}: surfaces [{surf}]")


@workflow_group.command(name="run")
@click.option("--workflow", "-w", "wf", required=True, help="Workflow name or path.")
@click.option("--events", "-e", default="",
              help="Comma-separated events, e.g. 'application_submitted,interview_result:pass'.")
def workflow_run(wf: str, events: str) -> None:
    """Dry-run a workflow through a sequence of events and print the stage trace."""
    try:
        w = load_workflow(wf)
    except WorkflowError as exc:
        raise click.ClickException(str(exc)) from exc
    evs = [e.strip() for e in events.split(",") if e.strip()]
    result = run_workflow(w, evs)
    click.secho(f"{w.name}", bold=True)
    for step in result.steps:
        click.echo(f"  → {click.style(step.label, fg='cyan')} "
                   f"(via {step.via}) — surfaces: [{', '.join(step.surfaces) or '—'}]")
        for a in step.actions:
            click.echo(click.style(f"      · {a}", dim=True))
    click.echo(f"  final: {result.final_stage}"
               + (f"  | ignored: {result.ignored}" if result.ignored else ""))


_STARTER = """# Ensayo single-company simulation config
company:
  name: "{{NAME}}"
  tagline: "A short company tagline"
  industry: "general"
  location: "Perth, Western Australia"
  profile:
    founded: 2018
    employees: 30
    description: |
      A one-paragraph description of what this fictional company does.
  scenario:
    type: "growth"
    name: "The central challenge"
    description: |
      The situation students step into — the tension that drives the scenario.
    key_tensions:
      - "First competing pressure"
      - "Second competing pressure"

theme: tech-modern
audience: adults
chatbot_mode: keyword

branding:
  colors:
    primary: "#4a63e7"
    accent: "#00d4aa"

employees:
  - name: "Alex Nguyen"
    role: "Managing Director"
    tier: executive
    archetype: founder_ceo
    customisation:
      background: |
        A short backstory for this person.
      personality_additions:
        - "Calm under pressure"
      knowledge_additions:
        - "Business strategy"
      opinions:
        - "We grow by keeping our reputation intact"

documents:
  - type: policy
    title: "Information Security Policy"
    brief: "Company-wide security policy covering acceptable use and access controls."
"""


if __name__ == "__main__":  # pragma: no cover
    main()
