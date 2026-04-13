"""Prompt assembly for AI content generation and chatbot prompts."""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from ensayo.models import BriefConfig, EmployeeSpec, Scenario


def _get_prompt_templates_dir() -> Path:
    """Get the path to the prompt templates directory."""
    return Path(str(importlib.resources.files("ensayo") / "templates" / "prompts"))


def _get_env() -> Environment:
    """Create a Jinja2 environment for prompt templates."""
    return Environment(
        loader=FileSystemLoader(str(_get_prompt_templates_dir())),
        autoescape=False,
        keep_trailing_newline=True,
    )


def render_backstory_system() -> str:
    """Render the system prompt for backstory generation."""
    env = _get_env()
    template = env.get_template("backstory_system.txt.j2")
    return template.render()


def render_backstory_user(
    *,
    company: dict[str, Any],
    scenario: dict[str, Any],
    employee: EmployeeSpec,
    archetype: dict[str, Any],
    other_employees: list[EmployeeSpec],
) -> str:
    """Render the user prompt for backstory generation."""
    env = _get_env()
    template = env.get_template("backstory_user.txt.j2")
    return template.render(
        company=company,
        scenario=scenario,
        employee=employee,
        archetype=archetype,
        other_employees=other_employees,
    )


def render_document_system() -> str:
    """Render the system prompt for document generation."""
    env = _get_env()
    template = env.get_template("document_system.txt.j2")
    return template.render()


def render_document_user(
    *,
    company: dict[str, Any],
    scenario: dict[str, Any],
    doc_title: str,
    doc_type: str,
    doc_brief: str = "",
    industry_context: dict[str, Any] | None = None,
    employees: list[EmployeeSpec],
) -> str:
    """Render the user prompt for document generation."""
    env = _get_env()
    template = env.get_template("document_user.txt.j2")
    return template.render(
        company=company,
        scenario=scenario,
        doc_title=doc_title,
        doc_type=doc_type,
        doc_brief=doc_brief,
        industry_context=industry_context,
        employees=employees,
    )


def render_chatbot_prompt(
    *,
    company: dict[str, Any],
    scenario: Scenario,
    employee: EmployeeSpec,
    archetype: dict[str, Any],
    prompt_extras: str = "",
) -> str:
    """Render a chatbot system prompt (deterministic, no AI call)."""
    env = _get_env()
    template = env.get_template("chatbot_prompt.txt.j2")
    return template.render(
        company=company,
        scenario=scenario,
        employee=employee,
        archetype=archetype,
        prompt_extras=prompt_extras,
    )


def render_job_system() -> str:
    """Render the system prompt for job posting generation."""
    env = _get_env()
    template = env.get_template("job_system.txt.j2")
    return template.render()


def render_job_user(
    *,
    company: dict[str, Any],
    scenario: dict[str, Any],
    job_title: str,
    department: str = "",
    location: str = "",
    employment_type: str = "Full-time",
    reports_to: str = "",
    job_brief: str = "",
    employees: list[EmployeeSpec],
) -> str:
    """Render the user prompt for job posting generation."""
    env = _get_env()
    template = env.get_template("job_user.txt.j2")
    return template.render(
        company=company,
        scenario=scenario,
        job_title=job_title,
        department=department,
        location=location,
        employment_type=employment_type,
        reports_to=reports_to,
        job_brief=job_brief,
        employees=employees,
    )


def brief_to_company_dict(brief: BriefConfig) -> dict[str, Any]:
    """Extract a company context dict from a BriefConfig for use in templates."""
    c = brief.company
    return {
        "name": c.name,
        "slug": c.slug,
        "industry": c.industry,
        "location": c.location,
        "founded": c.founded,
        "employees": c.employees,
        "revenue": c.revenue,
        "description": c.description,
        "key_facts": c.key_facts,
        "services": c.services,
    }


def brief_to_scenario_dict(brief: BriefConfig) -> dict[str, Any]:
    """Extract a scenario context dict from a BriefConfig for use in templates."""
    s = brief.scenario
    return {
        "name": s.name,
        "description": s.description,
        "key_tensions": s.key_tensions,
    }
