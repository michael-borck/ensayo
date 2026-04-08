"""Tests for prompt assembly (deterministic, no AI calls)."""

from ensayo.models import BriefConfig, CompanyProfile, EmployeeSpec, Scenario
from ensayo.prompts import (
    brief_to_company_dict,
    render_backstory_system,
    render_backstory_user,
    render_chatbot_prompt,
    render_document_user,
)
from ensayo.templates_data import load_archetype


def _make_brief() -> BriefConfig:
    return BriefConfig(
        company=CompanyProfile(
            name="Test Co",
            slug="test-co",
            industry="event_management",
            location="Perth",
            founded=2020,
            employees=20,
            revenue="$2M",
            description="A test company.",
            key_facts=["50 events per year"],
        ),
        scenario=Scenario(
            type="growth",
            name="Growing Pains",
            description="The company is expanding.",
            key_tensions=["Speed vs quality"],
        ),
    )


def _make_employee() -> EmployeeSpec:
    return EmployeeSpec(
        name="Jane Doe",
        role="Managing Director",
        archetype="founder_ceo",
        tier="executive",
    )


def test_backstory_system_prompt() -> None:
    prompt = render_backstory_system()
    assert "educational" in prompt.lower()
    assert "backstory" in prompt.lower()
    assert "frontmatter" in prompt.lower()


def test_backstory_user_prompt() -> None:
    brief = _make_brief()
    emp = _make_employee()
    archetype = load_archetype("founder_ceo")

    prompt = render_backstory_user(
        company=brief_to_company_dict(brief),
        scenario={"name": "Growing Pains", "description": "Expanding.", "key_tensions": []},
        employee=emp,
        archetype=archetype,
        other_employees=[],
    )
    assert "Jane Doe" in prompt
    assert "Managing Director" in prompt
    assert "Test Co" in prompt
    assert "Perth" in prompt


def test_chatbot_prompt_contains_key_elements() -> None:
    brief = _make_brief()
    emp = _make_employee()
    archetype = load_archetype("founder_ceo")

    prompt = render_chatbot_prompt(
        company=brief_to_company_dict(brief),
        scenario=brief.scenario,
        employee=emp,
        archetype=archetype,
        prompt_extras="Loves hiking on weekends.",
    )
    assert "Jane Doe" in prompt
    assert "Managing Director" in prompt
    assert "Test Co" in prompt
    assert "Stay in character" in prompt
    assert "hiking" in prompt


def test_document_user_prompt() -> None:
    brief = _make_brief()
    prompt = render_document_user(
        company=brief_to_company_dict(brief),
        scenario={"name": "Growth", "description": "Growing.", "key_tensions": []},
        doc_title="Operations Guide",
        doc_type="support",
        doc_brief="How we run things",
        employees=brief.employees,
    )
    assert "Operations Guide" in prompt
    assert "Test Co" in prompt
