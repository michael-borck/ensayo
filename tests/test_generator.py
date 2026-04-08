"""Tests for the content generation engine."""

from pathlib import Path
from unittest.mock import patch

from ensayo.generator import (
    generate_chatbot_prompt_file,
    generate_site_yaml,
    load_brief,
)
from ensayo.templates_data import list_archetypes, list_industries, load_archetype

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_brief() -> None:
    brief = load_brief(FIXTURES / "brief.yaml")
    assert brief.company.name == "Pinnacle Events"
    assert brief.company.industry == "event_management"
    assert brief.scenario.type == "growth"
    assert len(brief.employees) == 2
    assert brief.employees[0].name == "Sophie Anderson"
    assert brief.employees[0].archetype == "founder_ceo"
    assert brief.employees[0].refers_to["operations"] == "Rachel Martinez"
    assert "quality" in brief.employees[0].customisation.opinions[0].lower()


def test_generate_site_yaml() -> None:
    brief = load_brief(FIXTURES / "brief.yaml")
    site_yaml = generate_site_yaml(brief)
    assert site_yaml["company"]["name"] == "Pinnacle Events"
    assert site_yaml["company"]["slug"] == "pinnacle-events"
    assert site_yaml["branding"]["primary"] == "#8B4513"


def test_generate_chatbot_prompt_deterministic() -> None:
    brief = load_brief(FIXTURES / "brief.yaml")
    emp = brief.employees[0]
    archetype = load_archetype(emp.archetype)

    prompt = generate_chatbot_prompt_file(brief, emp, archetype)
    assert "Sophie Anderson" in prompt
    assert "Managing Director" in prompt
    assert "Pinnacle Events" in prompt
    assert "Stay in character" in prompt
    assert "Rachel Martinez" in prompt


def test_list_archetypes() -> None:
    archetypes = list_archetypes()
    assert "founder_ceo" in archetypes
    assert "operations_manager" in archetypes
    assert "finance_manager" in archetypes
    assert len(archetypes) >= 7


def test_list_industries() -> None:
    industries = list_industries()
    assert "event_management" in industries
    assert "cloud_services" in industries
    assert len(industries) >= 3


MOCK_BACKSTORY = """---
name: Sophie Anderson
slug: sophie-anderson
role: Managing Director
tier: executive
personality:
  - Warm
  - Decisive
knowledge:
  - Business strategy
refers_to:
  operations: Rachel Martinez
prompt_extras: Founded the company.
---

# Sophie Anderson

A backstory about Sophie."""


def test_generate_all_with_mocked_ai(tmp_path: Path) -> None:
    output = tmp_path / "content"

    with patch("ensayo.generator.generate_text", return_value=MOCK_BACKSTORY):
        from ensayo.generator import generate_all

        generate_all(FIXTURES / "brief.yaml", output)

    # Check employees were generated
    assert (output / "employees" / "sophie-anderson.md").is_file()
    assert (output / "employees" / "rachel-martinez.md").is_file()

    # Check prompts were generated
    assert (output / "employees" / "sophie-anderson-prompt.txt").is_file()

    # Check documents were generated (from industry defaults since no explicit docs in brief)
    assert (output / "docs" / "support").is_dir()

    # Check site.yaml was generated
    site_yaml = tmp_path / "site.yaml"
    assert site_yaml.is_file()
