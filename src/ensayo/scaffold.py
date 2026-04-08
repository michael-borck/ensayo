"""Scaffold a brief.yaml — interactive, minimal (AI-assisted), or fully automatic."""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.prompt import IntPrompt, Prompt

from ensayo.templates_data import list_archetypes, list_industries

console = Console()

SCENARIO_TYPES = ["growth", "breach", "digital_transformation", "crisis", "merger"]


def _get_prompt_env() -> Environment:
    """Get Jinja2 environment for prompt templates."""
    templates_dir = Path(str(importlib.resources.files("ensayo") / "templates" / "prompts"))
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=False,
        keep_trailing_newline=True,
    )


def _write_brief(brief: dict[str, Any], output: Path) -> None:
    """Write a brief.yaml file."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.dump(brief, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    console.print(f"[green bold]Wrote brief → {output}[/green bold]")


# --- Interactive mode ---


def _prompt_employee(index: int, archetypes: list[str]) -> dict[str, Any]:
    """Prompt for one employee's details."""
    console.print(f"\n[bold]Employee {index}[/bold]")
    name = Prompt.ask("  Name")
    role = Prompt.ask("  Role/Title")
    archetype = Prompt.ask(
        f"  Archetype [{', '.join(archetypes)}]",
        choices=archetypes,
    )
    tier = Prompt.ask(
        "  Tier", choices=["executive", "manager", "specialist"], default="specialist",
    )
    background = Prompt.ask("  Brief background (1-2 sentences)")

    slug = name.lower().replace(" ", "-")
    return {
        "id": slug,
        "name": name,
        "role": role,
        "archetype": archetype,
        "tier": tier,
        "customisation": {
            "years_at_company": 3,
            "years_in_industry": 8,
            "background": background,
        },
        "refers_to": {},
    }


def scaffold_interactive(output: Path) -> None:
    """Interactive wizard that asks questions and builds a brief.yaml."""
    industries = list_industries()
    archetypes = list_archetypes()

    console.print("[bold]Ensayo — New Simulation Scaffold[/bold]\n")

    # Company basics
    company_name = Prompt.ask("Company name")
    slug = company_name.lower().replace(" ", "-").replace("&", "and")
    tagline = Prompt.ask("Tagline", default="")
    industry = Prompt.ask(
        f"Industry [{', '.join(industries)}]",
        choices=industries,
    )
    location = Prompt.ask("Location", default="Perth, Western Australia")

    # Company profile
    founded = IntPrompt.ask("Year founded", default=2018)
    num_employees = IntPrompt.ask("Number of employees", default=25)
    revenue = Prompt.ask("Annual revenue", default="$5M annually")
    description = Prompt.ask("Company description (1-2 sentences)")

    # Scenario
    console.print(f"\n[bold]Scenario[/bold] (types: {', '.join(SCENARIO_TYPES)})")
    scenario_type = Prompt.ask("Scenario type", choices=SCENARIO_TYPES, default="growth")
    scenario_name = Prompt.ask("Scenario name", default="")
    scenario_desc = Prompt.ask("Scenario description (what's happening?)")

    # Branding
    primary = Prompt.ask("Primary brand colour (hex)", default="#2563eb")

    # Employees
    num_emps = IntPrompt.ask("\nHow many employees?", default=5)
    employees = []
    for i in range(1, num_emps + 1):
        employees.append(_prompt_employee(i, archetypes))

    brief: dict[str, Any] = {
        "company": {
            "name": company_name,
            "slug": slug,
            "tagline": tagline,
            "industry": industry,
            "location": location,
            "profile": {
                "founded": founded,
                "employees": num_employees,
                "revenue": revenue,
                "description": description,
                "key_facts": [],
                "services": [],
            },
            "scenario": {
                "type": scenario_type,
                "name": scenario_name or (
                    f"{company_name} — {scenario_type.replace('_', ' ').title()}"
                ),
                "description": scenario_desc,
                "key_tensions": [],
            },
        },
        "branding": {
            "colors": {
                "primary": primary,
                "secondary": primary,
                "accent": "#f59e0b",
            },
        },
        "employees": employees,
    }

    _write_brief(brief, output)
    console.print(
        "\n[dim]Edit the brief to add key_facts, services, tensions, "
        "and employee opinions before running content generation.[/dim]"
    )


# --- Minimal mode (AI fills in details) ---


def scaffold_minimal(
    company_name: str,
    industry: str,
    location: str = "Perth, Western Australia",
    scenario_type: str = "growth",
    output: Path = Path("brief.yaml"),
) -> None:
    """AI generates a full brief from just a company name and industry."""
    from ensayo.ai import generate_text

    env = _get_prompt_env()
    industries = list_industries()

    system_prompt = env.get_template("scaffold_minimal.txt.j2").render(
        industries=industries,
    )
    user_prompt = (
        f"Company name: {company_name}\n"
        f"Industry: {industry}\n"
        f"Location: {location}\n"
        f"Scenario type: {scenario_type}\n"
        f"\nGenerate the complete brief.yaml now."
    )

    with console.status("AI is designing the company..."):
        raw = generate_text(system_prompt, user_prompt, max_tokens=4096)

    brief = _parse_ai_yaml(raw)
    if brief:
        _write_brief(brief, output)
    else:
        # Write raw output for manual fixing
        output.write_text(raw, encoding="utf-8")
        console.print(
            "[yellow]AI output wasn't valid YAML. Wrote raw output — "
            "you may need to fix it manually.[/yellow]"
        )


# --- Auto mode (AI invents everything) ---


def scaffold_auto(
    industry: str,
    output: Path = Path("brief.yaml"),
) -> None:
    """AI invents an entire company from just an industry."""
    from ensayo.ai import generate_text

    env = _get_prompt_env()

    system_prompt = env.get_template("scaffold_auto.txt.j2").render(
        industry=industry,
    )
    user_prompt = (
        f"Industry: {industry}\n\n"
        f"Invent a complete, creative company and generate the brief.yaml now."
    )

    with console.status("AI is inventing a company..."):
        raw = generate_text(system_prompt, user_prompt, max_tokens=4096)

    brief = _parse_ai_yaml(raw)
    if brief:
        _write_brief(brief, output)
    else:
        output.write_text(raw, encoding="utf-8")
        console.print(
            "[yellow]AI output wasn't valid YAML. Wrote raw output — "
            "you may need to fix it manually.[/yellow]"
        )


def _parse_ai_yaml(raw: str) -> dict[str, Any] | None:
    """Try to parse YAML from AI output, stripping code fences if present."""
    text = raw.strip()

    # Strip markdown code fences if the AI included them
    if text.startswith("```"):
        # Remove opening fence (with optional language tag)
        first_newline = text.index("\n")
        text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-3].rstrip()

    try:
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
    except yaml.YAMLError:
        pass

    return None
