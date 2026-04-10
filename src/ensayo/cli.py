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


@main.command()
@click.option("--output", type=click.Path(), default="brief.yaml", help="Output file path")
@click.option("--minimal", is_flag=True, help="AI fills in details from name + industry")
@click.option("--auto", "auto_mode", is_flag=True, help="AI invents everything from industry")
@click.option("--name", "company_name", default="", help="Company name (for --minimal)")
@click.option(
    "--industry", default="",
    help="Industry ID (e.g. event_management, cloud_services, managed_it)",
)
@click.option("--location", default="Perth, Western Australia", help="Company location")
@click.option("--scenario", default="growth", help="Scenario type")
def scaffold(
    output: str,
    minimal: bool,
    auto_mode: bool,
    company_name: str,
    industry: str,
    location: str,
    scenario: str,
) -> None:
    """Scaffold a new brief.yaml — interactive, minimal (AI), or auto (AI)."""
    from ensayo.scaffold import scaffold_auto, scaffold_interactive, scaffold_minimal

    output_path = Path(output)

    if auto_mode:
        if not industry:
            from ensayo.templates_data import list_industries

            click.echo(f"Available industries: {', '.join(list_industries())}")
            industry = click.prompt("Industry")
        scaffold_auto(industry=industry, output=output_path)
    elif minimal:
        if not company_name:
            company_name = click.prompt("Company name")
        if not industry:
            from ensayo.templates_data import list_industries

            click.echo(f"Available industries: {', '.join(list_industries())}")
            industry = click.prompt("Industry")
        scaffold_minimal(
            company_name=company_name,
            industry=industry,
            location=location,
            scenario_type=scenario,
            output=output_path,
        )
    else:
        scaffold_interactive(output=output_path)


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


@content.command("add-job")
@click.option("--title", required=True, help="Job title")
@click.option("--department", default="", help="Department")
@click.option("--location", default="", help="Job location")
@click.option("--employment-type", default="Full-time", help="Employment type")
@click.option("--reports-to", default="", help="Name of the hiring manager")
@click.option("--instructions", default="", help="Instructions for content generation")
@click.option("--brief", type=click.Path(exists=True), default="brief.yaml", help="Brief file")
@click.option(
    "--content-dir", type=click.Path(), default="content",
    help="Content directory",
)
def content_add_job(
    title: str,
    department: str,
    location: str,
    employment_type: str,
    reports_to: str,
    instructions: str,
    brief: str,
    content_dir: str,
) -> None:
    """Add a job posting to an existing simulation."""
    from ensayo.generator import generate_single_job

    generate_single_job(
        Path(brief), Path(content_dir), title,
        department=department, location=location,
        employment_type=employment_type, reports_to=reports_to,
        instructions=instructions,
    )


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


@main.command("export-jobs")
@click.option(
    "--content-dir", type=click.Path(exists=True), default="content",
    help="Content directory",
)
@click.option(
    "--config", type=click.Path(), default="site.yaml",
    help="Site config file",
)
@click.option(
    "--brief", type=click.Path(), default="brief.yaml",
    help="Brief file (for reports_to and interview_pipeline metadata)",
)
@click.option(
    "--base-url", default="",
    help="Base URL of the deployed site (e.g. https://cloudcore.github.io)",
)
@click.option(
    "--output", type=click.Path(), default="jobs.json",
    help="Output JSON file",
)
def export_jobs(
    content_dir: str, config: str, brief: str, base_url: str, output: str,
) -> None:
    """Export job postings as JSON for external job board integration.

    Reads the AI-generated job descriptions from content/jobs/*.md and
    merges in brief.yaml metadata (reports_to, interview_pipeline) so
    downstream consumers like the WorkReady API can drive multi-stage
    interview pipelines.
    """
    import json

    import yaml

    from ensayo.content import load_job_postings, load_site_config

    config_path = Path(config)
    site = load_site_config(config_path) if config_path.is_file() else None

    # Load brief.yaml metadata if available — keyed by job title
    # (titles are more reliable than slugs because the AI sometimes
    # generates a different slug than ensayo's filename convention)
    brief_meta: dict[str, dict] = {}
    company_business_hours: dict | None = None
    brief_path = Path(brief)
    if brief_path.is_file():
        brief_data = yaml.safe_load(brief_path.read_text(encoding="utf-8")) or {}
        for j in brief_data.get("jobs", []):
            title = (j.get("title", "") or "").strip().lower()
            if title:
                brief_meta[title] = {
                    "reports_to": j.get("reports_to", ""),
                    "interview_pipeline": j.get("interview_pipeline"),
                    "additional_postings": j.get("additional_postings", []),
                    "blocking_override": j.get("blocking_override"),
                }
        # Optional per-company business hours override
        company_section = brief_data.get("company", {})
        bh = company_section.get("business_hours")
        if bh:
            company_business_hours = {
                "start": bh.get("start", 9),
                "end": bh.get("end", 17),
                "days": bh.get("days", [1, 2, 3, 4, 5]),
                "timezone": bh.get("timezone"),
                "description": bh.get("description", ""),
            }

    postings = load_job_postings(Path(content_dir))

    company_name = site.company.name if site else ""
    company_slug = site.company.slug if site else ""

    # Helper to convert "Marcus Webb" → "marcus-webb" matching ensayo's
    # employee filename convention. Strips honorifics and punctuation.
    def _name_to_slug(name: str) -> str:
        import re
        n = name.strip()
        # Strip honorifics (Dr., Mr., Mrs., Ms., Prof.)
        n = re.sub(r"^(Dr|Mr|Mrs|Ms|Prof)\.?\s+", "", n, flags=re.IGNORECASE)
        # Lowercase, remove punctuation, collapse whitespace to single dash
        n = re.sub(r"[^\w\s-]", "", n.lower())
        n = re.sub(r"\s+", "-", n).strip("-")
        return n

    employees_dir = Path(content_dir) / "employees"

    def _load_persona(person_name: str) -> str:
        """Load the chatbot prompt for an employee. Returns empty string if missing."""
        if not person_name:
            return ""
        slug = _name_to_slug(person_name)
        prompt_path = employees_dir / f"{slug}-prompt.txt"
        if prompt_path.is_file():
            return prompt_path.read_text(encoding="utf-8").strip()
        return ""

    jobs_list = []
    for job in postings:
        meta = brief_meta.get(job.title.strip().lower(), {})
        reports_to = meta.get("reports_to", "")
        entry = {
            "title": job.title,
            "slug": job.slug,
            "department": job.department,
            "location": job.location,
            "employment_type": job.employment_type,
            "url": f"{base_url}/careers/{job.slug}.html" if base_url else "",
            "description": job.body,
            "reports_to": reports_to,
            "manager_persona": _load_persona(reports_to),
        }
        if meta.get("interview_pipeline"):
            entry["interview_pipeline"] = meta["interview_pipeline"]
        if meta.get("additional_postings"):
            entry["additional_postings"] = meta["additional_postings"]
        if meta.get("blocking_override"):
            entry["blocking_override"] = meta["blocking_override"]
        jobs_list.append(entry)

    jobs_data = {
        "company": company_name,
        "company_slug": company_slug,
        "company_url": base_url,
        "jobs": jobs_list,
    }
    if company_business_hours:
        jobs_data["business_hours"] = company_business_hours

    out_path = Path(output)
    out_path.write_text(json.dumps(jobs_data, indent=2), encoding="utf-8")
    click.echo(f"Exported {len(postings)} jobs → {out_path}")


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
