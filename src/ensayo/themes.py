"""Theme discovery and manifest loading.

Themes are full Astro packages (spec §13). Each declares a ``theme.yaml`` with
its name, the configurations it supports, and the content props it consumes.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field

from .models import _Model


class ThemeError(Exception):
    """Raised when a theme is missing or its manifest is invalid."""


class ThemeManifest(_Model):
    name: str
    description: str = ""
    derived_from: str | None = None
    supports: dict = Field(default_factory=dict)
    features: list[str] = Field(default_factory=list)
    content_props: list[str] = Field(default_factory=list)


def default_themes_dir() -> Path:
    """Themes ship next to the package repo root (``<repo>/themes``)."""
    return Path(__file__).resolve().parents[2] / "themes"


def list_themes(themes_dir: Path) -> list[ThemeManifest]:
    if not themes_dir.exists():
        return []
    manifests: list[ThemeManifest] = []
    for child in sorted(themes_dir.iterdir()):
        manifest_path = child / "theme.yaml"
        if child.is_dir() and manifest_path.exists():
            manifests.append(load_manifest(manifest_path))
    return manifests


def resolve_theme(name: str, themes_dir: Path) -> Path:
    """Return the directory for *name*, raising :class:`ThemeError` if absent."""
    theme_dir = themes_dir / name
    if not theme_dir.is_dir():
        available = ", ".join(m.name for m in list_themes(themes_dir)) or "(none)"
        raise ThemeError(
            f"theme {name!r} not found in {themes_dir}. Available: {available}"
        )
    if not (theme_dir / "theme.yaml").exists():
        raise ThemeError(f"theme {name!r} is missing theme.yaml")
    if not (theme_dir / "package.json").exists():
        raise ThemeError(f"theme {name!r} is missing package.json (not an Astro package)")
    return theme_dir


def load_manifest(path: Path) -> ThemeManifest:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ThemeError(f"{path}: invalid YAML\n{exc}") from exc
    return ThemeManifest.model_validate(raw)
