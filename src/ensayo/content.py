"""Write generated content — both the canonical repo files and theme data.

Two outputs (spec §4.3):
  * Canonical repo content (``content/employees/*``, ``content/docs/*``) — the
    git-canonical source of truth a UC edits and the API reads at runtime.
  * Theme data (JSON/Markdown under the theme's ``src/data/``) — what Astro
    content collections consume to render the static site.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import CompanyConfig, Employee
from .prompts import (
    build_employee_markdown,
    build_keyword_responses,
    build_prompt,
)


def write_repo_content(config: CompanyConfig, root: Path) -> dict[str, int]:
    """Write the canonical ``content/`` tree under *root*. Returns a count manifest."""
    employees_dir = root / "content" / "employees"
    docs_dir = root / "content" / "docs"
    employees_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    for emp in config.employees:
        (employees_dir / f"{emp.slug}.md").write_text(
            build_employee_markdown(config, emp), encoding="utf-8"
        )
        (employees_dir / f"{emp.slug}-prompt.txt").write_text(
            build_prompt(config, emp), encoding="utf-8"
        )
        (employees_dir / f"{emp.slug}-keywords.json").write_text(
            json.dumps(build_keyword_responses(config, emp), indent=2), encoding="utf-8"
        )

    for doc in config.documents:
        (docs_dir / f"{doc.slug}.md").write_text(_doc_markdown(doc), encoding="utf-8")

    return {"employees": len(config.employees), "documents": len(config.documents)}


def write_theme_data(config: CompanyConfig, theme_src: Path) -> None:
    """Populate a theme's ``src/data/`` with this simulation's content.

    Clears any fixture data first so a build never mixes fixtures with real data.
    """
    data_dir = theme_src / "data"
    emp_dir = data_dir / "employees"
    doc_dir = data_dir / "docs"
    for d in (emp_dir, doc_dir):
        if d.exists():
            for f in d.glob("*"):
                if f.is_file():
                    f.unlink()
        d.mkdir(parents=True, exist_ok=True)

    (data_dir / "company.json").write_text(
        json.dumps(_company_payload(config), indent=2), encoding="utf-8"
    )

    for emp in config.employees:
        (emp_dir / f"{emp.slug}.json").write_text(
            json.dumps(_employee_payload(config, emp), indent=2), encoding="utf-8"
        )

    for doc in config.documents:
        (doc_dir / f"{doc.slug}.md").write_text(_doc_markdown(doc), encoding="utf-8")


def _company_payload(config: CompanyConfig) -> dict:
    c = config.company
    return {
        "name": c.name,
        "slug": c.slug,
        "tagline": c.tagline,
        "industry": c.industry,
        "location": c.location,
        "audience": config.audience.value,
        "chatbotMode": config.chatbot_mode.value,
        "theme": config.theme,
        "layout": config.layout,
        "branding": {"colors": config.branding.colors, "logo": config.branding.logo},
        "profile": {
            "founded": c.profile.founded,
            "employees": c.profile.employees,
            "revenue": c.profile.revenue,
            "structure": c.profile.structure,
            "description": c.profile.description.strip(),
            "keyFacts": c.profile.key_facts,
            "services": c.profile.services,
        },
        "scenario": {
            "type": c.scenario.type,
            "name": c.scenario.name,
            "description": c.scenario.description.strip(),
            "keyTensions": c.scenario.key_tensions,
        },
        "platform": {
            "bookingEnabled": config.platform.booking_enabled,
            "lecturerDashboard": config.platform.lecturer_dashboard,
        },
    }


def _employee_payload(config: CompanyConfig, emp: Employee) -> dict:
    cust = emp.customisation
    return {
        "slug": emp.slug,
        "name": emp.name,
        "role": emp.role,
        "title": emp.title,
        "tier": emp.tier.value,
        "department": emp.department,
        "archetype": emp.archetype,
        "yearsAtCompany": cust.years_at_company,
        "yearsInIndustry": cust.years_in_industry,
        "background": cust.background.strip(),
        "priorExperience": cust.prior_experience,
        "personality": cust.personality_additions,
        "knowledge": cust.knowledge_additions,
        "opinions": cust.opinions,
        "scenarioPerspective": cust.scenario_perspective.strip(),
        "refersTo": emp.refers_to,
        "chatbotMode": config.effective_chatbot_mode(emp).value,
        "chatbotEmbedId": emp.chatbot_embed_id,
        "anythingllm": {
            "baseUrl": config.anythingllm.base_url,
            "embedSrc": config.anythingllm.embed_src,
        },
        "keywords": build_keyword_responses(config, emp),
    }


def _doc_markdown(doc) -> str:
    body = doc.content.strip() if doc.content else _doc_stub(doc)
    fm = [
        "---",
        f'title: "{doc.title}"',
        f"type: {doc.type}",
        f'brief: "{doc.brief}"' if doc.brief else "brief: \"\"",
        "---",
    ]
    return "\n".join(fm) + "\n\n" + body + "\n"


def _doc_stub(doc) -> str:
    return (
        f"# {doc.title}\n\n"
        f"_{doc.brief}_\n\n"
        "> This document is a generated stub. A Unit Coordinator edits it in the "
        "dashboard, or LLM-assisted generation (Phase 2) drafts the full content."
    )
