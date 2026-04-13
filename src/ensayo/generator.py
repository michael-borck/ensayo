"""Content generation engine — generates backstories, documents, and prompts."""

from __future__ import annotations

import contextlib
import random
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

from ensayo.ai import generate_text
from ensayo.frontmatter import parse_frontmatter
from ensayo.models import (
    BrandingConfig,
    BriefConfig,
    ChatbotConfig,
    CompanyProfile,
    DocumentSpec,
    EmployeeCustomisation,
    EmployeeSpec,
    JobSpec,
    Scenario,
)
from ensayo.prompts import (
    brief_to_company_dict,
    brief_to_scenario_dict,
    render_backstory_system,
    render_backstory_user,
    render_chatbot_prompt,
    render_document_system,
    render_document_user,
    render_job_system,
    render_job_user,
)
from ensayo.templates_data import load_archetype, load_industry

console = Console()


def load_brief(brief_path: Path) -> BriefConfig:
    """Load and parse a brief.yaml file into a BriefConfig."""
    raw = yaml.safe_load(brief_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"brief.yaml must be a YAML mapping, got {type(raw).__name__}"
        raise ValueError(msg)

    # Company profile
    c = raw.get("company", {})
    profile_raw = c.get("profile", {})
    company = CompanyProfile(
        name=c.get("name", ""),
        slug=c.get("slug", ""),
        tagline=c.get("tagline", ""),
        industry=c.get("industry", ""),
        location=c.get("location", ""),
        founded=profile_raw.get("founded", 2020),
        employees=profile_raw.get("employees", 25),
        revenue=profile_raw.get("revenue", ""),
        structure=profile_raw.get("structure", "SME / Private"),
        description=profile_raw.get("description", ""),
        key_facts=profile_raw.get("key_facts", []),
        services=profile_raw.get("services", []),
    )

    # Scenario
    scenario_raw = c.get("scenario", {})
    scenario = Scenario(
        type=scenario_raw.get("type", "growth"),
        name=scenario_raw.get("name", ""),
        description=scenario_raw.get("description", ""),
        key_tensions=scenario_raw.get("key_tensions", []),
    )

    # Branding
    branding_raw = raw.get("branding", {})
    colors = branding_raw.get("colors", branding_raw)
    branding = BrandingConfig(
        primary=colors.get("primary", "#2563eb"),
        secondary=colors.get("secondary", "#1e40af"),
        accent=colors.get("accent", "#f59e0b"),
    )

    # Chatbot
    platform_raw = raw.get("platform", {})
    chatbot = ChatbotConfig(
        booking_enabled=platform_raw.get("booking_enabled", False),
    )

    # Employees
    employees: list[EmployeeSpec] = []
    for emp_raw in raw.get("employees", []):
        cust_raw = emp_raw.get("customisation", {})
        customisation = EmployeeCustomisation(
            years_at_company=cust_raw.get("years_at_company", 1),
            years_in_industry=cust_raw.get("years_in_industry", 5),
            background=cust_raw.get("background", ""),
            prior_experience=cust_raw.get("prior_experience", []),
            personality_additions=cust_raw.get("personality_additions", []),
            knowledge_additions=cust_raw.get("knowledge_additions", []),
            opinions=cust_raw.get("opinions", []),
            scenario_perspective=cust_raw.get("scenario_perspective", ""),
        )
        employees.append(EmployeeSpec(
            name=emp_raw.get("name", ""),
            role=emp_raw.get("role", ""),
            archetype=emp_raw.get("archetype", ""),
            slug=emp_raw.get("id", ""),
            tier=emp_raw.get("tier", "specialist"),
            customisation=customisation,
            refers_to=emp_raw.get("refers_to", {}),
        ))

    # Document requests
    documents: list[DocumentSpec] = []
    for doc_raw in raw.get("documents", []):
        documents.append(DocumentSpec(
            type=doc_raw.get("type", "support"),
            title=doc_raw.get("title", ""),
            brief=doc_raw.get("brief", ""),
        ))

    # Job postings
    jobs: list[JobSpec] = []
    for job_raw in raw.get("jobs", []):
        jobs.append(JobSpec(
            title=job_raw.get("title", ""),
            department=job_raw.get("department", ""),
            location=job_raw.get("location", ""),
            employment_type=job_raw.get("employment_type", "Full-time"),
            reports_to=job_raw.get("reports_to", ""),
            brief=job_raw.get("brief", ""),
        ))

    # Disciplines
    disciplines_raw = raw.get("disciplines", {})
    disciplines: dict[str, list[str]] = {}
    for level, items in disciplines_raw.items():
        if isinstance(items, list):
            disciplines[level] = [
                d.get("name", d) if isinstance(d, dict) else str(d)
                for d in items
            ]

    return BriefConfig(
        company=company,
        scenario=scenario,
        branding=branding,
        chatbot=chatbot,
        theme=raw.get("theme", "base"),
        layout=raw.get("layout", ""),
        employees=employees,
        documents=documents,
        jobs=jobs,
        disciplines=disciplines,
    )


def generate_employee_backstory(
    brief: BriefConfig,
    employee: EmployeeSpec,
    archetype: dict[str, Any],
    other_employees: list[EmployeeSpec],
) -> str:
    """Generate a backstory for an employee using AI. Returns raw markdown with frontmatter."""
    company_dict = brief_to_company_dict(brief)
    scenario_dict = brief_to_scenario_dict(brief)

    system_prompt = render_backstory_system()
    user_prompt = render_backstory_user(
        company=company_dict,
        scenario=scenario_dict,
        employee=employee,
        archetype=archetype,
        other_employees=other_employees,
    )

    return generate_text(system_prompt, user_prompt, max_tokens=4096)


def generate_document(
    brief: BriefConfig,
    doc_title: str,
    doc_type: str,
    doc_brief: str = "",
    industry_context: dict[str, Any] | None = None,
) -> str:
    """Generate a document using AI. Returns raw markdown with frontmatter."""
    company_dict = brief_to_company_dict(brief)
    scenario_dict = brief_to_scenario_dict(brief)

    system_prompt = render_document_system()
    user_prompt = render_document_user(
        company=company_dict,
        scenario=scenario_dict,
        doc_title=doc_title,
        doc_type=doc_type,
        doc_brief=doc_brief,
        industry_context=industry_context,
        employees=brief.employees,
    )

    return generate_text(system_prompt, user_prompt, max_tokens=4096)


def generate_job_posting(
    brief: BriefConfig,
    job_title: str,
    department: str = "",
    location: str = "",
    employment_type: str = "Full-time",
    reports_to: str = "",
    job_brief: str = "",
) -> str:
    """Generate a job posting using AI. Returns raw markdown with frontmatter."""
    company_dict = brief_to_company_dict(brief)
    scenario_dict = brief_to_scenario_dict(brief)

    system_prompt = render_job_system()
    user_prompt = render_job_user(
        company=company_dict,
        scenario=scenario_dict,
        job_title=job_title,
        department=department,
        location=location or brief.company.location,
        employment_type=employment_type,
        reports_to=reports_to,
        job_brief=job_brief,
        employees=brief.employees,
    )

    return generate_text(system_prompt, user_prompt, max_tokens=2048)


def generate_chatbot_prompt_file(
    brief: BriefConfig,
    employee: EmployeeSpec,
    archetype: dict[str, Any],
) -> str:
    """Generate a chatbot prompt.txt (deterministic, no AI call)."""
    company_dict = brief_to_company_dict(brief)
    return render_chatbot_prompt(
        company=company_dict,
        scenario=brief.scenario,
        employee=employee,
        archetype=archetype,
        prompt_extras=employee.customisation.scenario_perspective,
    )


CAREERS_LABELS = [
    "Careers",
    "Work With Us",
    "Join Our Team",
    "We're Hiring",
    "Open Positions",
    "Job Opportunities",
    "Come Work With Us",
    "Current Vacancies",
    "Your Next Role",
]


def generate_site_yaml(brief: BriefConfig) -> dict[str, Any]:
    """Extract the slim site.yaml config from a brief."""
    site: dict[str, Any] = {
        "company": {
            "name": brief.company.name,
            "slug": brief.company.slug,
            "tagline": brief.company.tagline,
        },
        "theme": brief.theme,
        "branding": {
            "primary": brief.branding.primary,
            "secondary": brief.branding.secondary,
            "accent": brief.branding.accent,
        },
        "chatbot": {
            "mode": brief.chatbot.mode,
            "platform": brief.chatbot.platform,
            "booking_enabled": brief.chatbot.booking_enabled,
            "booking_api": brief.chatbot.booking_api,
        },
    }

    if brief.layout:
        site["layout"] = brief.layout

    if brief.jobs:
        site["careers"] = {
            "label": random.choice(CAREERS_LABELS),  # noqa: S311
            "submit_url": "",
            "show_apply_form": True,
        }

    return site


def _write_content_file(path: Path, content: str) -> None:
    """Write generated content to a file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_all(brief_path: Path, output_dir: Path) -> None:
    """Generate all content from a brief — employees, documents, prompts, site.yaml."""
    brief = load_brief(brief_path)
    industry_id = brief.company.industry
    industry: dict[str, Any] | None = None

    if industry_id:
        try:
            industry = load_industry(industry_id)
        except ValueError:
            console.print(f"[yellow]Warning: Unknown industry '{industry_id}', skipping.[/yellow]")

    output_dir.mkdir(parents=True, exist_ok=True)
    employees_dir = output_dir / "employees"
    support_dir = output_dir / "docs" / "support"
    policy_dir = output_dir / "docs" / "policy"

    # --- Generate employee backstories ---
    console.print(f"[bold]Generating {len(brief.employees)} employee backstories...[/bold]")
    for emp in brief.employees:
        archetype: dict[str, Any] = {}
        if emp.archetype:
            try:
                archetype = load_archetype(emp.archetype)
            except ValueError:
                console.print(
                    f"[yellow]Warning: Unknown archetype '{emp.archetype}' "
                    f"for {emp.name}[/yellow]"
                )

        others = [e for e in brief.employees if e.name != emp.name]

        with console.status(f"Generating backstory: {emp.name}..."):
            raw = generate_employee_backstory(brief, emp, archetype, others)

        _write_content_file(employees_dir / f"{emp.slug}.md", raw)
        console.print(f"  [green]+ {emp.name}[/green] → employees/{emp.slug}.md")

        # Generate chatbot prompt
        prompt = generate_chatbot_prompt_file(brief, emp, archetype)
        _write_content_file(employees_dir / f"{emp.slug}-prompt.txt", prompt)

    # --- Generate documents ---
    # Collect document specs: explicit from brief + defaults from industry
    doc_specs: list[DocumentSpec] = list(brief.documents)

    if industry and not brief.documents:
        std_docs = industry.get("standard_documents", {})
        for doc_raw in std_docs.get("support", []):
            doc_specs.append(DocumentSpec(
                type="support",
                title=doc_raw.get("title", ""),
                brief=doc_raw.get("brief", ""),
            ))
        for doc_raw in std_docs.get("policies", []):
            doc_specs.append(DocumentSpec(
                type="policy",
                title=doc_raw.get("title", ""),
                brief=doc_raw.get("brief", ""),
            ))

    if doc_specs:
        console.print(f"[bold]Generating {len(doc_specs)} documents...[/bold]")
        for doc_spec in doc_specs:
            slug = doc_spec.title.lower().replace(" ", "-").replace("&", "and")
            dest_dir = support_dir if doc_spec.type == "support" else policy_dir

            with console.status(f"Generating document: {doc_spec.title}..."):
                raw = generate_document(
                    brief,
                    doc_title=doc_spec.title,
                    doc_type=doc_spec.type,
                    doc_brief=doc_spec.brief,
                    industry_context=industry,
                )

            _write_content_file(dest_dir / f"{slug}.md", raw)
            console.print(
                f"  [green]+ {doc_spec.title}[/green] → docs/{doc_spec.type}/{slug}.md"
            )

    # --- Generate job postings ---
    if brief.jobs:
        jobs_dir = output_dir / "jobs"
        console.print(f"[bold]Generating {len(brief.jobs)} job postings...[/bold]")
        for job_spec in brief.jobs:
            slug = job_spec.title.lower().replace(" ", "-").replace("&", "and")

            with console.status(f"Generating job posting: {job_spec.title}..."):
                raw = generate_job_posting(
                    brief,
                    job_title=job_spec.title,
                    department=job_spec.department,
                    location=job_spec.location,
                    employment_type=job_spec.employment_type,
                    reports_to=job_spec.reports_to,
                    job_brief=job_spec.brief,
                )

            _write_content_file(jobs_dir / f"{slug}.md", raw)
            console.print(
                f"  [green]+ {job_spec.title}[/green] → jobs/{slug}.md"
            )

    # --- Generate site.yaml ---
    site_yaml = generate_site_yaml(brief)
    site_yaml_path = output_dir.parent / "site.yaml"
    site_yaml_path.write_text(yaml.dump(site_yaml, default_flow_style=False), encoding="utf-8")
    console.print(f"[green]+ site.yaml[/green] → {site_yaml_path}")

    console.print("[bold green]Content generation complete.[/bold green]")


def generate_single_employee(
    brief_path: Path,
    content_dir: Path,
    name: str,
    role: str,
    archetype_id: str,
) -> None:
    """Add a single employee to existing content."""
    brief = load_brief(brief_path)

    archetype: dict[str, Any] = {}
    if archetype_id:
        archetype = load_archetype(archetype_id)

    slug = name.lower().replace(" ", "-")
    emp = EmployeeSpec(
        name=name,
        role=role,
        archetype=archetype_id,
        slug=slug,
    )
    others = brief.employees

    with console.status(f"Generating backstory: {name}..."):
        raw = generate_employee_backstory(brief, emp, archetype, others)

    path = content_dir / "employees" / f"{slug}.md"
    _write_content_file(path, raw)
    console.print(f"[green]+ {name}[/green] → {path}")

    prompt = generate_chatbot_prompt_file(brief, emp, archetype)
    prompt_path = content_dir / "employees" / f"{slug}-prompt.txt"
    _write_content_file(prompt_path, prompt)
    console.print(f"[green]+ prompt[/green] → {prompt_path}")


def generate_single_document(
    brief_path: Path,
    content_dir: Path,
    doc_type: str,
    title: str,
    instructions: str = "",
) -> None:
    """Add a single document to existing content."""
    brief = load_brief(brief_path)

    industry: dict[str, Any] | None = None
    if brief.company.industry:
        with contextlib.suppress(ValueError):
            industry = load_industry(brief.company.industry)

    slug = title.lower().replace(" ", "-").replace("&", "and")
    dest_dir = content_dir / "docs" / doc_type

    with console.status(f"Generating document: {title}..."):
        raw = generate_document(
            brief,
            doc_title=title,
            doc_type=doc_type,
            doc_brief=instructions,
            industry_context=industry,
        )

    path = dest_dir / f"{slug}.md"
    _write_content_file(path, raw)
    console.print(f"[green]+ {title}[/green] → {path}")


def generate_single_job(
    brief_path: Path,
    content_dir: Path,
    title: str,
    department: str = "",
    location: str = "",
    employment_type: str = "Full-time",
    reports_to: str = "",
    instructions: str = "",
) -> None:
    """Add a single job posting to existing content."""
    brief = load_brief(brief_path)

    slug = title.lower().replace(" ", "-").replace("&", "and")
    dest_dir = content_dir / "jobs"

    with console.status(f"Generating job posting: {title}..."):
        raw = generate_job_posting(
            brief,
            job_title=title,
            department=department,
            location=location,
            employment_type=employment_type,
            reports_to=reports_to,
            job_brief=instructions,
        )

    path = dest_dir / f"{slug}.md"
    _write_content_file(path, raw)
    console.print(f"[green]+ {title}[/green] → {path}")


def regenerate_prompts(brief_path: Path, content_dir: Path) -> None:
    """Regenerate chatbot prompt.txt files from existing backstories."""
    brief = load_brief(brief_path)
    employees_dir = content_dir / "employees"

    if not employees_dir.is_dir():
        console.print("[yellow]No employees directory found.[/yellow]")
        return

    count = 0
    for emp_spec in brief.employees:
        backstory_path = employees_dir / f"{emp_spec.slug}.md"
        if not backstory_path.is_file():
            console.print(f"[yellow]Skipping {emp_spec.name}: no backstory file[/yellow]")
            continue

        archetype: dict[str, Any] = {}
        if emp_spec.archetype:
            with contextlib.suppress(ValueError):
                archetype = load_archetype(emp_spec.archetype)

        # Read backstory to extract any prompt_extras from frontmatter
        text = backstory_path.read_text(encoding="utf-8")
        meta, _body = parse_frontmatter(text)
        extras = str(meta.get("prompt_extras", emp_spec.customisation.scenario_perspective))

        prompt = render_chatbot_prompt(
            company=brief_to_company_dict(brief),
            scenario=brief.scenario,
            employee=emp_spec,
            archetype=archetype,
            prompt_extras=extras,
        )

        prompt_path = employees_dir / f"{emp_spec.slug}-prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        console.print(f"  [green]+ {emp_spec.name}[/green] → {prompt_path.name}")
        count += 1

    console.print(f"[bold green]Regenerated {count} prompts.[/bold green]")
