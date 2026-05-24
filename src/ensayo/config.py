"""Load and validate ``company.yaml`` into a :class:`CompanyConfig`."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import CompanyConfig


class ConfigError(Exception):
    """Raised when a simulation config cannot be loaded or is invalid."""


def load_company_config(path: str | Path) -> CompanyConfig:
    """Read a YAML config file and return a validated :class:`CompanyConfig`.

    Raises :class:`ConfigError` with a human-readable message on any failure.
    """
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - passthrough formatting
        raise ConfigError(f"{path}: invalid YAML\n{exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top-level YAML must be a mapping")

    try:
        return CompanyConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(path, exc)) from exc


def dump_config_yaml(config: CompanyConfig) -> str:
    """Serialise a (possibly enriched) config back to clean YAML."""
    data = config.model_dump(mode="json", exclude_defaults=True)
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


def _format_validation_error(path: Path, exc: ValidationError) -> str:
    lines = [f"{path}: {exc.error_count()} validation error(s)"]
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        lines.append(f"  - {loc}: {err['msg']}")
    return "\n".join(lines)
