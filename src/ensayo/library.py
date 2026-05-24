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


class Industry(_Model):
    name: str
    label: str = ""
    context: str = ""
    norms: list[str] = Field(default_factory=list)


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


def list_archetypes(library_dir: Path | None = None) -> list[Archetype]:
    return sorted(_archetype_index(library_dir or _LIBRARY_DIR).values(), key=lambda a: a.name)


def list_industries(library_dir: Path | None = None) -> list[Industry]:
    return sorted(_industry_index(library_dir or _LIBRARY_DIR).values(), key=lambda i: i.name)
