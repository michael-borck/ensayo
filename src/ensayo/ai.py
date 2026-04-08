"""Thin wrapper around the Anthropic API for content generation."""

from __future__ import annotations

import os


def _get_model() -> str:
    """Get the model to use for content generation."""
    return os.environ.get("ENSAYO_MODEL", "claude-sonnet-4-20250514")


def generate_text(system: str, user: str, max_tokens: int = 4096) -> str:
    """Call the Anthropic API and return the text response.

    Requires the `anthropic` package (install with `pip install ensayo[content]`).
    Requires ANTHROPIC_API_KEY environment variable.
    """
    try:
        import anthropic
    except ImportError:
        msg = (
            "The 'anthropic' package is required for content generation. "
            "Install it with: pip install ensayo[content]"
        )
        raise ImportError(msg) from None

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=_get_model(),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    # Extract text from the response
    text_parts: list[str] = []
    for block in message.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)

    return "\n".join(text_parts)
