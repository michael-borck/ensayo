"""CLI entry point for ensayo."""

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
    click.echo(f"Initialising simulation from {brief} → {output}")
    click.echo("Not yet implemented.")


@main.group()
def content() -> None:
    """Content generation commands."""


@content.command("generate")
@click.option("--brief", type=click.Path(exists=True), required=True, help="Path to brief.yaml")
@click.option("--output", type=click.Path(), required=True, help="Output content directory")
def content_generate(brief: str, output: str) -> None:
    """Generate all content from a brief using AI."""
    click.echo(f"Generating content from {brief} → {output}")
    click.echo("Not yet implemented.")


@content.command("add-employee")
@click.option("--name", required=True, help="Employee name")
@click.option("--role", required=True, help="Employee role/title")
@click.option("--archetype", required=True, help="Role archetype (e.g. founder_ceo)")
def content_add_employee(name: str, role: str, archetype: str) -> None:
    """Add an employee to an existing simulation."""
    click.echo(f"Adding employee: {name} ({role}) using archetype {archetype}")
    click.echo("Not yet implemented.")


@content.command("add-doc")
@click.option("--type", "doc_type", required=True, type=click.Choice(["support", "policy"]))
@click.option("--title", required=True, help="Document title")
@click.option("--instructions", default="", help="Instructions for content generation")
def content_add_doc(doc_type: str, title: str, instructions: str) -> None:
    """Add a document to an existing simulation."""
    click.echo(f"Adding {doc_type} document: {title}")
    click.echo("Not yet implemented.")


@content.command("prompts")
@click.option(
    "--content-dir", type=click.Path(exists=True), default="content",
    help="Content directory",
)
def content_prompts(content_dir: str) -> None:
    """Regenerate chatbot prompts from backstories."""
    click.echo(f"Regenerating prompts from {content_dir}")
    click.echo("Not yet implemented.")


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
    click.echo(f"Building site: {config} + {content_dir} → {output}")
    click.echo("Not yet implemented.")


@main.command("export-booking-config")
@click.option(
    "--content-dir", type=click.Path(exists=True), default="content",
    help="Content directory",
)
@click.option(
    "--output", type=click.Path(), default="booking-employees.json",
    help="Output JSON file",
)
def export_booking_config(content_dir: str, output: str) -> None:
    """Export employee config for the booking API."""
    click.echo(f"Exporting booking config from {content_dir} → {output}")
    click.echo("Not yet implemented.")
