"""CLI entry point for ensayo."""

from pathlib import Path

import click

from ensayo import __version__


@click.group()
@click.version_option(version=__version__, prog_name="ensayo")
def main() -> None:
    """Ensayo — generator for educational company simulation sites."""


@main.command()
@click.option("--brief", type=click.Path(exists=True), required=True, help="Path to brief.yaml")
@click.option("--output", type=click.Path(), required=True, help="Output directory")
def init(brief: str, output: str) -> None:
    """Generate content and build a simulation site from a brief."""
    from ensayo.builder import build_site
    from ensayo.generator import generate_all

    output_path = Path(output)
    content_dir = output_path / "content"
    dist_dir = output_path / "dist"

    # Step 1: Generate content
    generate_all(Path(brief), content_dir)

    # Step 2: Build site (site.yaml is written by generate_all next to content/)
    site_yaml = output_path / "site.yaml"
    if site_yaml.is_file():
        build_site(site_yaml, content_dir, dist_dir)


@main.group()
def content() -> None:
    """Content generation commands."""


@content.command("generate")
@click.option("--brief", type=click.Path(exists=True), required=True, help="Path to brief.yaml")
@click.option("--output", type=click.Path(), required=True, help="Output content directory")
def content_generate(brief: str, output: str) -> None:
    """Generate all content from a brief using AI."""
    from ensayo.generator import generate_all

    generate_all(Path(brief), Path(output))


@content.command("add-employee")
@click.option("--brief", type=click.Path(exists=True), default="brief.yaml", help="Brief file")
@click.option(
    "--content-dir", type=click.Path(), default="content",
    help="Content directory",
)
@click.option("--name", required=True, help="Employee name")
@click.option("--role", required=True, help="Employee role/title")
@click.option("--archetype", required=True, help="Role archetype (e.g. founder_ceo)")
def content_add_employee(
    brief: str, content_dir: str, name: str, role: str, archetype: str,
) -> None:
    """Add an employee to an existing simulation."""
    from ensayo.generator import generate_single_employee

    generate_single_employee(Path(brief), Path(content_dir), name, role, archetype)


@content.command("add-doc")
@click.option("--type", "doc_type", required=True, type=click.Choice(["support", "policy"]))
@click.option("--title", required=True, help="Document title")
@click.option("--instructions", default="", help="Instructions for content generation")
@click.option("--brief", type=click.Path(exists=True), default="brief.yaml", help="Brief file")
@click.option(
    "--content-dir", type=click.Path(), default="content",
    help="Content directory",
)
def content_add_doc(
    doc_type: str, title: str, instructions: str, brief: str, content_dir: str,
) -> None:
    """Add a document to an existing simulation."""
    from ensayo.generator import generate_single_document

    generate_single_document(Path(brief), Path(content_dir), doc_type, title, instructions)


@content.command("prompts")
@click.option(
    "--content-dir", type=click.Path(exists=True), default="content",
    help="Content directory",
)
@click.option("--brief", type=click.Path(exists=True), default="brief.yaml", help="Brief file")
def content_prompts(content_dir: str, brief: str) -> None:
    """Regenerate chatbot prompts from backstories."""
    from ensayo.generator import regenerate_prompts

    regenerate_prompts(Path(brief), Path(content_dir))


@main.command()
@click.option(
    "--config", type=click.Path(exists=True), default="site.yaml",
    help="Site config file",
)
@click.option(
    "--content-dir", type=click.Path(exists=True), default="content",
    help="Content directory",
)
@click.option("--output", type=click.Path(), default="dist", help="Output directory")
def build(config: str, content_dir: str, output: str) -> None:
    """Build a vanilla HTML site from content and config."""
    from ensayo.builder import build_site

    build_site(Path(config), Path(content_dir), Path(output))


@main.command("export-booking-config")
@click.option(
    "--content-dir", type=click.Path(exists=True), default="content",
    help="Content directory",
)
@click.option(
    "--config", type=click.Path(), default="site.yaml",
    help="Site config file (for simulation metadata)",
)
@click.option(
    "--output", type=click.Path(), default="booking-employees.json",
    help="Output JSON file",
)
def export_booking_config(content_dir: str, config: str, output: str) -> None:
    """Export employee config for the booking API."""
    from ensayo.booking import export_booking_config as do_export

    config_path = Path(config) if Path(config).is_file() else None
    do_export(Path(content_dir), config_path, Path(output))
