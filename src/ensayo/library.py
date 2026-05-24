"""Role-archetype and industry libraries (the building blocks of personas).

Archetypes and industries are shipped as YAML under ``library/`` and loaded into
typed models. They feed the layered prompt builder (archetype → industry →
company → individual). Unknown names fall back to the generic ``staff`` /
``general`` entries so generation never hard-fails on a typo.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field

from .models import _Model

_LIBRARY_DIR = Path(__file__).resolve().parent / "library"

GENERIC_ARCHETYPE = "staff"
GENERIC_INDUSTRY = "general"
GENERIC_DOCUMENT = "custom"


class KeywordSeed(_Model):
    keywords: list[str] = Field(default_factory=list)
    response: str = ""


class Archetype(_Model):
    name: str
    label: str = ""
    default_tier: str = "staff"
    communication_style: str = ""
    personality: list[str] = Field(default_factory=list)
    knowledge: list[str] = Field(default_factory=list)
    prompt_fragment: str = ""
    keyword_seeds: list[KeywordSeed] = Field(default_factory=list)
    referral_topics: list[str] = Field(default_factory=list)
    mature: bool = False  # filtered out of minors-audience simulations (spec §7.6)


class Industry(_Model):
    name: str
    label: str = ""
    context: str = ""
    norms: list[str] = Field(default_factory=list)


class ScenarioTemplate(_Model):
    name: str
    label: str = ""
    summary: str = ""
    default_tensions: list[str] = Field(default_factory=list)
    prompt_hint: str = ""


class DocumentTemplate(_Model):
    type: str
    label: str = ""
    structure: list[str] = Field(default_factory=list)
    prompt_hint: str = ""


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@lru_cache(maxsize=None)
def _archetype_index(library_dir: Path) -> dict[str, Archetype]:
    out: dict[str, Archetype] = {}
    d = library_dir / "archetypes"
    if d.exists():
        for f in d.glob("*.yaml"):
            a = Archetype.model_validate(_load_yaml(f))
            out[a.name] = a
    return out


@lru_cache(maxsize=None)
def _industry_index(library_dir: Path) -> dict[str, Industry]:
    out: dict[str, Industry] = {}
    d = library_dir / "industries"
    if d.exists():
        for f in d.glob("*.yaml"):
            i = Industry.model_validate(_load_yaml(f))
            out[i.name] = i
    return out


def load_archetype(name: str, library_dir: Path | None = None) -> Archetype:
    """Return the archetype for *name*, or the generic ``staff`` fallback."""
    index = _archetype_index(library_dir or _LIBRARY_DIR)
    if name in index:
        return index[name]
    return index.get(GENERIC_ARCHETYPE, Archetype(name=GENERIC_ARCHETYPE, label="Team Member"))


def load_industry(name: str, library_dir: Path | None = None) -> Industry:
    """Return the industry for *name*, or the generic ``general`` fallback."""
    index = _industry_index(library_dir or _LIBRARY_DIR)
    if name in index:
        return index[name]
    return index.get(GENERIC_INDUSTRY, Industry(name=GENERIC_INDUSTRY, label="General Business"))


@lru_cache(maxsize=None)
def _scenario_index(library_dir: Path) -> dict[str, ScenarioTemplate]:
    out: dict[str, ScenarioTemplate] = {}
    d = library_dir / "scenarios"
    if d.exists():
        for f in d.glob("*.yaml"):
            s = ScenarioTemplate.model_validate(_load_yaml(f))
            out[s.name] = s
    return out


@lru_cache(maxsize=None)
def _document_index(library_dir: Path) -> dict[str, DocumentTemplate]:
    out: dict[str, DocumentTemplate] = {}
    d = library_dir / "documents"
    if d.exists():
        for f in d.glob("*.yaml"):
            t = DocumentTemplate.model_validate(_load_yaml(f))
            out[t.type] = t
    return out


def load_scenario_template(name: str, library_dir: Path | None = None) -> ScenarioTemplate | None:
    """Return the scenario template for *name*, or ``None`` if there's no match."""
    return _scenario_index(library_dir or _LIBRARY_DIR).get(name)


def load_document_template(doc_type: str, library_dir: Path | None = None) -> DocumentTemplate:
    """Return the document template for *doc_type*, or the generic ``custom`` fallback."""
    index = _document_index(library_dir or _LIBRARY_DIR)
    if doc_type in index:
        return index[doc_type]
    return index.get(GENERIC_DOCUMENT, DocumentTemplate(type=GENERIC_DOCUMENT, label="Document"))


def filter_mature(archetypes: list[Archetype]) -> list[Archetype]:
    """Drop archetypes flagged mature (for minors audiences, spec §7.6)."""
    return [a for a in archetypes if not a.mature]


def list_archetypes(library_dir: Path | None = None, *, include_mature: bool = True) -> list[Archetype]:
    items = sorted(_archetype_index(library_dir or _LIBRARY_DIR).values(), key=lambda a: a.name)
    return items if include_mature else filter_mature(items)


def list_industries(library_dir: Path | None = None) -> list[Industry]:
    return sorted(_industry_index(library_dir or _LIBRARY_DIR).values(), key=lambda i: i.name)
