"""Tests for frontmatter parser."""

from ensayo.frontmatter import parse_frontmatter


def test_basic_frontmatter() -> None:
    text = "---\ntitle: Hello\n---\nBody text"
    meta, body = parse_frontmatter(text)
    assert meta["title"] == "Hello"
    assert body == "Body text"


def test_no_frontmatter() -> None:
    text = "Just some text without frontmatter"
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_empty_frontmatter() -> None:
    text = "---\n---\nBody only"
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert "Body only" in body


def test_complex_frontmatter() -> None:
    text = """---
name: Jane Doe
role: Manager
personality:
  - Warm
  - Decisive
refers_to:
  finance: John Smith
---

# Backstory content here"""
    meta, body = parse_frontmatter(text)
    assert meta["name"] == "Jane Doe"
    assert meta["personality"] == ["Warm", "Decisive"]
    assert meta["refers_to"]["finance"] == "John Smith"
    assert "Backstory content" in body


def test_no_closing_delimiter() -> None:
    text = "---\ntitle: Broken"
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert body == text
