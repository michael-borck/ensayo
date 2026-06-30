"""Turn an idea (or extracted file content) into simulation proposals.

Calls the configured LLM provider to propose 2–3 distinct simulations as
structured JSON. When no real provider is configured (stub) or parsing fails,
falls back to template proposals derived from keywords — so ideation always
returns something usable, with or without an API key.

A proposal is a plain dict shaped for the dashboard editors:

    {title, oneliner, pattern, audience, theme, workflow,
     company:{name, tagline, industry, location, profile:{description},
              scenario:{type, name, description}},
     companies:[...],            # only for pattern == "multi"
     employees:[{name, role, archetype, style}], include_docs, pros, cons}
"""

from __future__ import annotations

import json
import re
from typing import Any

from .llm import get_provider

_MAX_CONTENT_CHARS = 6000  # keep the prompt bounded

# A small palette for the template fallback (keyword → flavour).
_THEMES = ["tech-modern", "finance-traditional", "mining-rugged", "nfp-warm",
           "government-formal", "advisory-cool"]
_INDUSTRIES = ["software_development", "finance", "mining", "nonprofit",
               "government", "consulting"]
_SCENARIOS = ["growth", "breach", "digital_transformation", "crisis", "merger"]


class IdeateError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


_SYSTEM = (
    "You design workplace teaching simulations. Given a lecturer's idea or source "
    "material, propose distinct, teachable simulations. Be concrete and specific "
    "to the material. Respond with ONLY a JSON object: "
    '{"proposals":[...]}, no prose. Each proposal: '
    '{"title","oneliner","pattern" (single|multi|safe),"theme","industry",'
    '"scenario_type","company_name","employees":[{name,role,archetype,quirk}],'
    '"include_docs" (bool),"pros":[...],"cons":[...]}. '
    "Provide 2-3 proposals that differ in pattern or angle.")


def ideate(idea: str = "", content: str = "") -> list[dict]:
    """Return 2–3 simulation proposals derived from *idea* and/or *content*."""
    blob = "\n\n".join(s for s in (idea.strip(), content.strip()) if s)
    if not blob:
        raise IdeateError("Describe an idea or upload a file to suggest simulations.")
    blob = blob[:_MAX_CONTENT_CHARS]

    provider, spec = get_provider()
    if spec.provider != "stub":
        try:
            res = provider.generate(_prompt(blob), system=_SYSTEM, max_tokens=1800,
                                     temperature=0.8)
            proposals = _parse(res.text)
            if proposals:
                return [_normalise(p, blob) for p in proposals][:3]
        except Exception:  # fall through to template proposals
            pass
    return _template_proposals(blob)


def _prompt(blob: str) -> str:
    return ("Propose 2-3 distinct workplace teaching simulations based on this "
            "idea/source material. Tailor company name, industry, scenario, and "
            "the people to the material. Include one single-company, and vary the "
            "others (e.g. a multi-site, or a school-safe 'safe' variant). For "
            "each, give honest pros/cons (note if the material suits a simulation "
            "style or not).\n\n--- MATERIAL ---\n" + blob)


# --- LLM output parsing ----------------------------------------------------

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse(text: str) -> list[dict]:
    if not text:
        return []
    m = _JSON_RE.search(text)
    raw = m.group(0) if m else text
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    proposals = data.get("proposals") if isinstance(data, dict) else None
    return proposals if isinstance(proposals, list) else []


def _normalise(p: Any, blob: str) -> dict:
    """Coerce an LLM proposal (or a template dict) into the editor-shaped dict."""
    p = p if isinstance(p, dict) else {}
    pattern = str(p.get("pattern", "single")).lower()
    if pattern not in {"single", "multi", "safe"}:
        pattern = "single"
    audience = "minors" if pattern == "safe" else "adults"
    theme = str(p.get("theme") or _guess(blob, _THEMES, "tech-modern"))
    industry = str(p.get("industry") or _guess(blob, _INDUSTRIES, "general"))
    employees = []
    for e in (p.get("employees") or [])[:8]:
        if isinstance(e, dict):
            employees.append({
                "name": str(e.get("name", "")).strip() or "New hire",
                "role": str(e.get("role", "")).strip(),
                "archetype": str(e.get("archetype", "")).strip() or "staff",
            })
    base_company = {
        "name": str(p.get("company_name") or _company_name(blob)),
        "tagline": "", "industry": industry, "location": "",
        "profile": {"description": ""},
        "scenario": {"type": str(p.get("scenario_type") or _guess(blob, _SCENARIOS, "growth")),
                     "name": str(p.get("title") or "The central challenge"),
                     "description": str(p.get("oneliner") or "")},
    }
    if not employees:
        employees = _seed_employees(industry)
    out: dict = {
        "title": str(p.get("title") or base_company["name"]),
        "oneliner": str(p.get("oneliner") or "A workplace scenario drawn from your material."),
        "pattern": pattern, "audience": audience, "theme": theme, "workflow": "",
        "company": base_company, "employees": employees,
        "include_docs": bool(p.get("include_docs", True)),
        "pros": [str(x) for x in (p.get("pros") or [])][:4],
        "cons": [str(x) for x in (p.get("cons") or [])][:4],
    }
    if pattern == "multi":
        out["companies"] = [_company_for_multi(base_company, i, theme, industry) for i in range(2)]
    return out


# --- template fallback (no LLM key) ----------------------------------------

def _template_proposals(blob: str) -> list[dict]:
    """2–3 grounded proposals derived from keywords when no LLM is configured."""
    theme = _guess(blob, _THEMES, "tech-modern")
    industry = _guess(blob, _INDUSTRIES, "software_development")
    scen = _guess(blob, _SCENARIOS, "growth")
    co = _company_name(blob)
    single = _normalise({
        "title": f"{co}: a single-company case",
        "oneliner": f"Students explore {co} as one organisation facing a {scen} scenario.",
        "pattern": "single", "theme": theme, "industry": industry,
        "scenario_type": scen, "company_name": co,
        "pros": ["Focused narrative; easy to scope for one class.",
                 "Every employee shares the scenario context."],
        "cons": ["Less variety than a multi-company setting."],
    }, blob)
    multi = _normalise({
        "title": f"{co} & partners: a multi-site sector",
        "oneliner": "A portal coordinating several related companies students move between.",
        "pattern": "multi", "theme": theme, "industry": industry,
        "scenario_type": scen, "company_name": co,
        "pros": ["Richer ecosystem; supports applications, a job board, a workflow.",
                 "Great for capstone / multi-week units."],
        "cons": ["More to set up; heavier to build (portal + each company).",
                 "Better suited to advanced cohorts."],
    }, blob)
    safe = _normalise({
        "title": f"{co} (school-safe): keyword chatbots, no PII",
        "oneliner": "A minors-safe variant: deterministic chatbots, shared-password sign-in.",
        "pattern": "safe", "theme": theme, "industry": industry,
        "scenario_type": scen, "company_name": co,
        "pros": ["Safe for under-18s; no personal data collected.",
                 "Works offline of any LLM provider."],
        "cons": ["No LLM depth; keyword-only conversations.",
                 "Single-company only."],
    }, blob)
    return [single, multi, safe]


def _guess(blob: str, options: list[str], default: str) -> str:
    low = blob.lower()
    for opt in options:
        if opt in low:
            return opt
        for tok in opt.replace("_", " ").replace("-", " ").split():
            if len(tok) > 3 and tok in low:  # match on a meaningful token (e.g. "mining" → mining-rugged)
                return opt
    return default

def _company_name(blob: str) -> str:
    words = re.findall(r"[A-Z][a-z]+", blob)
    if not words:
        return "Acme Co"
    return (words[0] + (" " + words[1] if len(words) > 1 else "") + " Co")[:40]


def _seed_employees(industry: str) -> list[dict]:
    return [
        {"name": "Alex Morgan", "role": "Managing Director", "archetype": "founder_ceo"},
        {"name": "Sam Rivera", "role": "Operations Manager", "archetype": "operations_manager"},
    ]


def _company_for_multi(section: dict, i: int, theme: str, industry: str) -> dict:
    """Build a CompanyConfig-shaped dict (a company section + theme + employees)."""
    suffix = ["North", "South"][i % 2]
    s = {**section, "name": f"{section['name']} {suffix}"}
    return {"company": s, "theme": theme, "audience": "adults",
            "employees": _seed_employees(industry)}
