"""Safe Mode — the minors-safe defaults bundle and override reporting (spec §7).

The audience setting (`adults` | `minors`) is a *bundle of defaults*, not a single
flag. For `minors`, each subsystem defaults to its safest setting. A UC may
deviate, but only by explicitly acknowledging the override (listed in
``CompanyConfig.audience_overrides``), which the dashboard surfaces as a persistent
banner and the platform records in the audit log.

This module is the single source of truth for what the bundle contains and which
overrides are currently active.
"""

from __future__ import annotations

from .models import Audience, CompanyConfig

# Ordered bundle: each entry is one subsystem, its override key, and the safe
# default applied under `audience: minors`.
MINORS_BUNDLE: list[dict] = [
    {"key": "llm_chatbots", "label": "LLM chatbots", "safe": "keyword chatbots only"},
    {"key": "individual_accounts", "label": "Individual accounts", "safe": "shared password only (no PII)"},
    {"key": "messaging", "label": "Messaging surface", "safe": "disabled"},
    {"key": "inbox", "label": "Inbox / portal", "safe": "disabled (single-company only)"},
    {"key": "group_chat", "label": "Group chat", "safe": "disabled"},
    {"key": "conversations", "label": "1-on-1 LLM conversations", "safe": "disabled"},
    {"key": "file_upload", "label": "Task file upload", "safe": "text-only submissions"},
    {"key": "multi_site", "label": "Multi-site mode", "safe": "disabled (single-company only)"},
    {"key": "llm_assist", "label": "LLM-assisted content generation", "safe": "off by default (hard-confirm)"},
]

_KEYS = {b["key"] for b in MINORS_BUNDLE}


def valid_override(key: str) -> bool:
    return key in _KEYS


def acknowledged(config: CompanyConfig, key: str) -> bool:
    """True if *key* is an acknowledged override (only meaningful for minors)."""
    return config.audience is Audience.minors and key in config.audience_overrides


def audience_report(config: CompanyConfig) -> dict:
    """Describe the audience configuration: the bundle, and any active overrides.

    ``safe`` is True when no overrides are active (a school IT admin can verify a
    simulation is minors-safe by checking that, spec §7.4)."""
    if config.audience is not Audience.minors:
        return {"audience": "adults", "safe": True, "overrides": [], "bundle": []}

    ack = [k for k in config.audience_overrides if k in _KEYS]
    unknown = [k for k in config.audience_overrides if k not in _KEYS]
    overrides = [b for b in MINORS_BUNDLE if b["key"] in ack]
    return {
        "audience": "minors",
        "safe": len(ack) == 0,
        "overrides": overrides,
        "unknown_overrides": unknown,
        "bundle": MINORS_BUNDLE,
    }
