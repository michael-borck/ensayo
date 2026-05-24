"""``ensayo`` command-line interface."""

from __future__ import annotations

from pathlib import Path

import click

from . import __version__
from .config import ConfigError, dump_config_yaml, load_company_config
from .enrich import enrich_config, estimate
from .generator import GenerationError, generate
from .llm import get_provider
from .themes import ThemeError, default_themes_dir, list_themes

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
    """Generate a static simulation site from a company.yaml."""
    try:
        result = generate(
            config, output, theme=theme, themes_dir=themes_dir, base=base,
            with_llm=with_llm or force_llm, force_llm=force_llm,
            build=not no_build, log=lambda m: click.echo(click.style("  " + m, dim=True)),
        )
    except (ConfigError, ThemeError, GenerationError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.secho("✓ Generation complete", fg="green", bold=True)
    if result.built and result.dist_dir:
        click.echo(f"  Static site: {result.dist_dir}")
        click.echo(f"  Preview:     python3 -m http.server -d {result.dist_dir} 8000")
    else:
        click.echo(f"  Content written to {result.output_dir} (build skipped)")


@main.command()
@click.option("--config", "-c", required=True, type=click.Path(path_type=Path))
def validate(config: Path) -> None:
    """Validate a company.yaml without generating anything."""
    try:
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
@click.option("--output", "-o", default="./company.yaml", type=click.Path(path_type=Path))
@click.option("--name", default="Acme Corp", help="Company name to seed the file with.")
def init(output: Path, name: str) -> None:
    """Write a starter company.yaml to edit."""
    if output.exists():
        raise click.ClickException(f"{output} already exists — refusing to overwrite.")
    output.write_text(_STARTER.replace("{{NAME}}", name), encoding="utf-8")
    click.secho(f"✓ Wrote starter config to {output}", fg="green")
    click.echo("  Edit it, then run: ensayo generate -c " + str(output))


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
