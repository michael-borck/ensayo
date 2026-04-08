"""Tests for scaffold command."""

from pathlib import Path
from unittest.mock import patch

import yaml

from ensayo.scaffold import _parse_ai_yaml, scaffold_auto, scaffold_minimal

MOCK_BRIEF_YAML = """\
company:
  name: "Coastal Medical Centre"
  slug: "coastal-medical"
  tagline: "Healthcare for the community"
  industry: "healthcare"
  location: "Brisbane, Australia"
  profile:
    founded: 2015
    employees: 35
    revenue: "$8M annually"
    structure: "SME / Private"
    description: |
      A community medical centre facing digital transformation.
    key_facts:
      - "12,000 patients annually"
    services:
      - "General practice"
      - "Allied health"
  scenario:
    type: "digital_transformation"
    name: "Going Digital"
    description: |
      Transitioning from paper records to a new EHR system.
    key_tensions:
      - "Staff resistance vs efficiency gains"
branding:
  colors:
    primary: "#1a7a5c"
    secondary: "#2b9c7a"
    accent: "#a8d8c0"
employees:
  - id: "dr-sarah-nguyen"
    name: "Dr Sarah Nguyen"
    role: "Practice Director"
    archetype: "founder_ceo"
    tier: "executive"
    customisation:
      years_at_company: 10
      years_in_industry: 20
      background: |
        Founded the practice after 10 years in hospital medicine.
      personality_additions:
        - "Patient-focused"
      knowledge_additions:
        - "Clinical operations"
      opinions:
        - "Technology should serve patients, not the other way around"
      scenario_perspective: |
        Supportive but worried about disruption.
    refers_to:
      operations: "Mike Chen"
"""

MOCK_BRIEF_WITH_FENCES = f"```yaml\n{MOCK_BRIEF_YAML}```"


def test_parse_ai_yaml_clean() -> None:
    result = _parse_ai_yaml(MOCK_BRIEF_YAML)
    assert result is not None
    assert result["company"]["name"] == "Coastal Medical Centre"
    assert len(result["employees"]) == 1


def test_parse_ai_yaml_with_fences() -> None:
    result = _parse_ai_yaml(MOCK_BRIEF_WITH_FENCES)
    assert result is not None
    assert result["company"]["name"] == "Coastal Medical Centre"


def test_parse_ai_yaml_invalid() -> None:
    result = _parse_ai_yaml("this is not yaml: [[[")
    assert result is None


def test_scaffold_minimal_with_mocked_ai(tmp_path: Path) -> None:
    output = tmp_path / "brief.yaml"

    with patch("ensayo.ai.generate_text", return_value=MOCK_BRIEF_YAML):
        scaffold_minimal(
            company_name="Coastal Medical",
            industry="cloud_services",
            output=output,
        )

    assert output.is_file()
    data = yaml.safe_load(output.read_text())
    assert data["company"]["name"] == "Coastal Medical Centre"
    assert len(data["employees"]) >= 1


def test_scaffold_auto_with_mocked_ai(tmp_path: Path) -> None:
    output = tmp_path / "brief.yaml"

    with patch("ensayo.ai.generate_text", return_value=MOCK_BRIEF_YAML):
        scaffold_auto(industry="event_management", output=output)

    assert output.is_file()
    data = yaml.safe_load(output.read_text())
    assert "company" in data
    assert "employees" in data


def test_scaffold_auto_handles_fenced_yaml(tmp_path: Path) -> None:
    output = tmp_path / "brief.yaml"

    with patch("ensayo.ai.generate_text", return_value=MOCK_BRIEF_WITH_FENCES):
        scaffold_auto(industry="event_management", output=output)

    assert output.is_file()
    data = yaml.safe_load(output.read_text())
    assert data["company"]["name"] == "Coastal Medical Centre"
