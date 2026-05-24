"""Per-surface stub content generators (spec §8.7).

Stub mode is not one generic responder — each content surface has its own
tone-appropriate generator, so ``--with-llm`` produces useful, grounded skeletons
even with no provider configured. The output is deliberately marked as a draft so
it's obvious it should be reviewed or regenerated with a real provider.
"""

from __future__ import annotations

from .library import Archetype, DocumentTemplate, ScenarioTemplate
from .models import CompanyConfig, Document, Employee


def stub_backstory(config: CompanyConfig, employee: Employee, archetype: Archetype) -> str:
    company = config.company
    role = employee.role or archetype.label
    style = archetype.communication_style or "professional and approachable"
    return (
        f"{employee.name} is the {role} at {company.name}"
        f"{(' in ' + company.location) if company.location else ''}. "
        f"They have built up real experience in this role and are known for being "
        f"{style.lower()} "
        f"As {role.lower()}, they focus on the parts of the business that matter "
        f"most to their work and care about doing it well.\n\n"
        f"_(Draft backstory generated in stub mode — regenerate with an LLM "
        f"provider, or edit, for a richer persona.)_"
    )


def stub_opinions(config: CompanyConfig, employee: Employee, archetype: Archetype) -> list[str]:
    base = [s.response for s in archetype.keyword_seeds[:2] if s.response]
    if config.company.scenario.name:
        base.append(
            f"The {config.company.scenario.name.lower()} is the thing on my mind "
            f"right now."
        )
    return base or ["I care about doing my part of the work well."]


def stub_scenario_perspective(config: CompanyConfig, employee: Employee, archetype: Archetype) -> str:
    scenario = config.company.scenario
    topic = scenario.name or "the current situation"
    return (
        f"From where I sit as {employee.role or archetype.label}, {topic.lower()} "
        f"affects my work directly. I see both the opportunity and the risk, and I "
        f"have a clear view on what we should do next. "
        f"_(Draft — regenerate with an LLM provider for depth.)_"
    )


def stub_scenario_description(config: CompanyConfig, template: ScenarioTemplate | None) -> str:
    company = config.company
    if template:
        return (
            f"{company.name} is facing a {template.label.lower()} situation. "
            f"{template.summary} Students step into this and must navigate the "
            f"competing pressures it creates.\n\n"
            f"_(Draft scenario generated in stub mode — regenerate with an LLM "
            f"provider for a richer narrative.)_"
        )
    return (
        f"{company.name} is navigating a significant challenge that shapes the "
        f"work of everyone in the organisation.\n\n_(Draft — regenerate with an LLM.)_"
    )


def stub_document(config: CompanyConfig, doc: Document, template: DocumentTemplate) -> str:
    company = config.company
    lines = [f"# {doc.title}", ""]
    if doc.brief:
        lines += [f"_{doc.brief}_", ""]
    for section in template.structure or ["Overview", "Detail", "Summary"]:
        lines.append(f"## {section}")
        lines.append(
            f"This section covers {section.lower()} for {company.name}. "
            f"(Draft content — generate with an LLM provider, or edit directly.)"
        )
        lines.append("")
    return "\n".join(lines).strip()
