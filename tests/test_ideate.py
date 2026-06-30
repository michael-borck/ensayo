"""Ideation: file extraction + proposal generation + endpoint."""

from __future__ import annotations

import io

import pytest

from ensayo.extract import ExtractError, extract_text
from ensayo.ideate import ideate


# --- extraction ------------------------------------------------------------

def test_extract_text_file():
    assert extract_text(b"hello\nworld", "notes.txt") == "hello\nworld"


def test_extract_markdown_and_quarto_are_text():
    assert extract_text(b"# Title\nbody", "a.md").startswith("# Title")
    assert extract_text(b"---\ntitle: x\n---", "a.qmd")


def test_extract_unsupported_type():
    with pytest.raises(ExtractError):
        extract_text(b"x", "archive.zip")


def test_extract_truncates_huge_text():
    out = extract_text(b"x" * 100_000, "big.txt")
    assert len(out) == 24000  # char_limit cap


# --- ideation (stub/template fallback — deterministic without an LLM key) ---

def test_ideate_returns_three_distinct_patterns():
    props = ideate("A fintech startup hit by a data breach", "")
    assert len(props) == 3
    assert {p["pattern"] for p in props} == {"single", "multi", "safe"}


def test_ideate_proposal_shapes():
    props = ideate("A hospital management crisis with staff conflicts", "")
    single = next(p for p in props if p["pattern"] == "single")
    assert single["company"]["name"]
    assert single["theme"]
    assert len(single["employees"]) >= 1
    assert single["pros"] and single["cons"]
    multi = next(p for p in props if p["pattern"] == "multi")
    assert len(multi["companies"]) == 2
    safe = next(p for p in props if p["pattern"] == "safe")
    assert safe["audience"] == "minors"


def test_ideate_uses_content_too():
    props = ideate("", "A mining company facing an environmental incident review.")
    assert len(props) == 3
    # mining keyword should nudge the theme toward mining-rugged
    assert any(p["theme"] == "mining-rugged" for p in props)


def test_ideate_requires_some_input():
    with pytest.raises(Exception):
        ideate("", "")


# --- endpoint --------------------------------------------------------------

def test_ideate_endpoint_idea(client, auth):
    r = client.post("/api/v1/ideate", headers=auth, data={"idea": "a data breach response"})
    assert r.status_code == 200, r.text
    assert len(r.json()["proposals"]) == 3


def test_ideate_endpoint_file_upload(client, auth):
    r = client.post("/api/v1/ideate", headers=auth, data={"idea": ""},
                    files={"file": ("brief.txt", io.BytesIO(b"a marketing campaign simulation"), "text/plain")})
    assert r.status_code == 200, r.text
    assert len(r.json()["proposals"]) == 3


def test_ideate_endpoint_empty(client, auth):
    assert client.post("/api/v1/ideate", headers=auth, data={"idea": ""}).status_code == 400


def test_ideate_endpoint_unsupported_file(client, auth):
    r = client.post("/api/v1/ideate", headers=auth, data={"idea": ""},
                    files={"file": ("a.zip", io.BytesIO(b"x"), "application/zip")})
    assert r.status_code == 415


def test_ideate_requires_auth(client):
    assert client.post("/api/v1/ideate", data={"idea": "x"}).status_code == 401
