"""Load archetype and industry template data from package resources."""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import Any

import yaml


def _get_data_dir(subdir: str) -> Path:
    """Get the path to a package data directory."""
    return Path(str(importlib.resources.files("ensayo") / subdir))


def load_archetype(archetype_id: str) -> dict[str, Any]:
    """Load an archetype YAML file by ID."""
    path = _get_data_dir("archetypes") / f"{archetype_id}.yaml"
    if not path.is_file():
        msg = f"Unknown archetype: {archetype_id}"
        raise ValueError(msg)
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def load_industry(industry_id: str) -> dict[str, Any]:
    """Load an industry template YAML file by ID."""
    path = _get_data_dir("industries") / f"{industry_id}.yaml"
    if not path.is_file():
        msg = f"Unknown industry: {industry_id}"
        raise ValueError(msg)
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def list_archetypes() -> list[str]:
    """List available archetype IDs."""
    archetypes_dir = _get_data_dir("archetypes")
    return sorted(p.stem for p in archetypes_dir.glob("*.yaml"))


def list_industries() -> list[str]:
    """List available industry IDs."""
    industries_dir = _get_data_dir("industries")
    return sorted(p.stem for p in industries_dir.glob("*.yaml"))
