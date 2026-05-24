"""Bulk LLM-assisted content generation (spec §10.6).

Walks a config, finds content that's missing (or, with ``force``, everything),
and generates it in one pass: employee backstories, opinions, and scenario
perspectives; the scenario narrative; and document bodies. Reports a token-count
estimate up front and recovers from per-item failures (one bad call doesn't sink
the batch).

This is the engine the Phase 3 dashboard's job-based ``/api/v1/jobs/bulk-generate``
endpoint will wrap; here it's exposed via the CLI (``ensayo enrich`` and
``ensayo generate --with-llm``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from . import stubs
from .library import (
    load_archetype,
    load_document_template,
    load_scenario_template,
)
from .llm import LLMError, LLMProvider, ProviderSpec
from .models import CompanyConfig

# Rough (input, output) token costs per generated item, for pre-run estimates.
_EST = {
    "backstory": (320, 260),
    "opinions": (220, 90),
    "perspective": (260, 140),
    "scenario": (280, 280),
    "document": (280, 430),
}

ProgressFn = Callable[["GenItem", str], None]


@dataclass
class GenItem:
    kind: str
    label: str
    status: str = "pending"  # pending | generated | failed
    error: str = ""


@dataclass
class EnrichmentResult:
    config: CompanyConfig
    items: list[GenItem] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def generated(self) -> int:
        return sum(1 for i in self.items if i.status == "generated")

    @property
    def failed(self) -> int:
        return sum(1 for i in self.items if i.status == "failed")


@dataclass
class _Plan:
    kind: str
    label: str
    system: str
    prompt: str
    stub: Callable[[], object]
    apply: Callable[[object], None]


def _company_context(config: CompanyConfig) -> str:
    c = config.company
    parts = [f"Company: {c.name}"]
    if c.tagline:
        parts.append(f"Tagline: {c.tagline}")
    if c.industry:
        parts.append(f"Industry: {c.industry}")
    if c.location:
        parts.append(f"Location: {c.location}")
    if c.profile.description:
        parts.append(f"About: {c.profile.description.strip()}")
    if c.scenario.name:
        parts.append(f"Scenario: {c.scenario.name}")
    if c.scenario.description:
        parts.append(f"Situation: {c.scenario.description.strip()}")
    return "\n".join(parts)


def _parse_bullets(text: str, limit: int = 4) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip().lstrip("-*•0123456789.) ").strip()
        if s:
            out.append(s)
    return out[:limit]


def _plan(config: CompanyConfig, force: bool) -> list[_Plan]:
    """The single source of what-needs-generating, shared by estimate + run."""
    plans: list[_Plan] = []
    ctx = _company_context(config)
    c = config.company

    # --- scenario narrative -------------------------------------------------
    scen = c.scenario
    if force or not scen.description.strip():
        tmpl = load_scenario_template(scen.type)
        hint = tmpl.prompt_hint if tmpl else "Write a realistic workplace scenario."

        def apply_scen(text, scen=scen, tmpl=tmpl):
            scen.description = str(text).strip()
            if tmpl and not scen.key_tensions:
                scen.key_tensions = list(tmpl.default_tensions)

        plans.append(_Plan(
            "scenario", f"Scenario: {scen.name or scen.type}",
            "You write concise, believable scenarios for workplace teaching simulations.",
            f"{ctx}\n\n{hint}\n\nWrite 1-2 paragraphs. Do not use headings.",
            lambda tmpl=tmpl: stubs.stub_scenario_description(config, tmpl),
            apply_scen,
        ))

    # --- employees ----------------------------------------------------------
    for emp in config.employees:
        arche = load_archetype(emp.archetype)
        cust = emp.customisation
        role = emp.role or arche.label
        emp_ctx = f"{ctx}\n\nPerson: {emp.name}, {role}. Role type: {arche.label}."

        if force or not cust.background.strip():
            def apply_bg(text, cust=cust):
                cust.background = str(text).strip()

            plans.append(_Plan(
                "backstory", f"{emp.name} — backstory",
                "You write believable employee backstories for teaching simulations.",
                f"{emp_ctx}\n\nWrite a 2-3 paragraph backstory for this person: their "
                f"experience, how they came to the company, and how they work. "
                f"Do not write in the first person. No headings.",
                lambda emp=emp, arche=arche: stubs.stub_backstory(config, emp, arche),
                apply_bg,
            ))

        if force or not cust.opinions:
            def apply_op(value, cust=cust):
                cust.opinions = value if isinstance(value, list) else _parse_bullets(value)

            plans.append(_Plan(
                "opinions", f"{emp.name} — views",
                "You capture a person's candid professional opinions for a simulation.",
                f"{emp_ctx}\n\nList 3-4 short, candid opinions this person holds about "
                f"the company's current situation. One per line, no numbering.",
                lambda emp=emp, arche=arche: stubs.stub_opinions(config, emp, arche),
                apply_op,
            ))

        if force or not cust.scenario_perspective.strip():
            def apply_pp(text, cust=cust):
                cust.scenario_perspective = str(text).strip()

            plans.append(_Plan(
                "perspective", f"{emp.name} — perspective",
                "You write a person's perspective on their company's situation.",
                f"{emp_ctx}\n\nWrite a short paragraph (3-4 sentences) on how this "
                f"person sees the current situation. No headings.",
                lambda emp=emp, arche=arche: stubs.stub_scenario_perspective(config, emp, arche),
                apply_pp,
            ))

    # --- documents ----------------------------------------------------------
    for doc in config.documents:
        if force or not doc.content.strip():
            tmpl = load_document_template(doc.type)

            def apply_doc(text, doc=doc):
                doc.content = str(text).strip()

            brief = f"Brief: {doc.brief}" if doc.brief else ""
            plans.append(_Plan(
                "document", f"Document: {doc.title}",
                "You write realistic internal company documents for teaching simulations.",
                f"{ctx}\n\nDocument type: {tmpl.label}. Title: {doc.title}. {brief}\n\n"
                f"{tmpl.prompt_hint}\n\nSuggested sections: "
                f"{', '.join(tmpl.structure)}. Use Markdown headings.",
                lambda doc=doc, tmpl=tmpl: stubs.stub_document(config, doc, tmpl),
                apply_doc,
            ))

    return plans


def estimate(config: CompanyConfig, *, force: bool = False) -> dict:
    """Return a token-count estimate for the work bulk generation would do."""
    plans = _plan(config, force)
    ti = to = 0
    by_kind: dict[str, int] = {}
    for p in plans:
        i, o = _EST.get(p.kind, (250, 250))
        ti += i
        to += o
        by_kind[p.kind] = by_kind.get(p.kind, 0) + 1
    return {"items": len(plans), "input_tokens": ti, "output_tokens": to,
            "by_kind": by_kind}


def enrich_config(
    config: CompanyConfig, provider: LLMProvider, spec: ProviderSpec, *,
    force: bool = False, on_progress: ProgressFn | None = None,
) -> EnrichmentResult:
    """Generate missing content into *config* in place. Recovers per-item."""
    result = EnrichmentResult(config=config)
    is_stub = spec.provider == "stub"

    for plan in _plan(config, force):
        item = GenItem(kind=plan.kind, label=plan.label)
        result.items.append(item)
        if on_progress:
            on_progress(item, "start")
        try:
            if is_stub:
                value: object = plan.stub()
            else:
                res = provider.generate(plan.prompt, system=plan.system, max_tokens=1200)
                result.input_tokens += res.input_tokens
                result.output_tokens += res.output_tokens
                if not res.text.strip():
                    raise LLMError("empty response from provider")
                value = res.text
            plan.apply(value)
            item.status = "generated"
        except Exception as exc:  # noqa: BLE001 — batch resilience: never abort the run
            item.status = "failed"
            item.error = str(exc)
        if on_progress:
            on_progress(item, "done")

    return result
