"""Parse YAML frontmatter from markdown files."""

from __future__ import annotations

from pathlib import Path

import yaml


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Split YAML frontmatter from markdown body.

    Expects content in the form:
        ---
        key: value
        ---
        Markdown body here...

    Returns (metadata_dict, body_string). If no frontmatter is found,
    returns an empty dict and the full text as body.
    """
    text = text.strip()

    # Strip code fences that AI models sometimes wrap around output
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    if not text.startswith("---"):
        return {}, text

    # Find the closing ---
    end = text.find("---", 3)
    if end == -1:
        return {}, text

    frontmatter_str = text[3:end].strip()
    body = text[end + 3 :].strip()

    meta = yaml.safe_load(frontmatter_str)
    if not isinstance(meta, dict):
        return {}, text

    return meta, body


def load_frontmatter_file(path: Path) -> tuple[dict[str, object], str]:
    """Read a file and parse its frontmatter.

    Returns (metadata_dict, body_string).
    """
    text = path.read_text(encoding="utf-8")
    return parse_frontmatter(text)
