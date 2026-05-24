"""Phase 1 tests: archetype/industry library and the layered prompt builder."""

from pathlib import Path

from ensayo.config import load_company_config
from ensayo.library import (
    list_archetypes,
    load_archetype,
    load_industry,
)
from ensayo.models import ChatbotMode
from ensayo.prompts import build_keyword_responses, build_prompt

REPO = Path(__file__).resolve().parents[1]
NEXUS = REPO / "examples" / "nexuspoint" / "company.yaml"
TECHNOVA = REPO / "examples" / "technova" / "company.yaml"


def test_archetype_library_loads():
    names = {a.name for a in list_archetypes()}
    # 10 roles + the generic staff fallback.
    assert "staff" in names
    assert "founder_ceo" in names
    assert "technical_specialist" in names
    assert len(names) >= 11


def test_unknown_archetype_falls_back_to_staff():
    a = load_archetype("does-not-exist")
    assert a.name == "staff"


def test_known_industry_loads():
    i = load_industry("cloud_services")
    assert i.context
    assert "cloud" in i.label.lower()


def test_layered_prompt_includes_all_four_layers():
    cfg = load_company_config(NEXUS)
    marcus = next(e for e in cfg.employees if e.slug == "marcus-webb")  # technical_specialist
    prompt = build_prompt(cfg, marcus)
    # individual layer
    assert "Marcus Webb" in prompt
    # company layer
    assert "NexusPoint Systems" in prompt
    # industry layer
    assert "INDUSTRY CONTEXT:" in prompt
    # archetype layer
    assert "YOUR ROLE:" in prompt
    assert "technical expert" in prompt.lower()


def test_personality_merges_archetype_and_individual():
    cfg = load_company_config(NEXUS)
    alex = next(e for e in cfg.employees if e.slug == "alex-nguyen")  # founder_ceo
    prompt = build_prompt(cfg, alex)
    # from archetype
    assert "Decisive but consultative" in prompt
    # from individual customisation
    assert "Calm and measured under pressure" in prompt


def test_keyword_responses_seed_from_archetype():
    cfg = load_company_config(NEXUS)
    alex = next(e for e in cfg.employees if e.slug == "alex-nguyen")
    kw = build_keyword_responses(cfg, alex)
    joined = " ".join(r["response"] for r in kw["rules"])
    # founder_ceo seed about strategy/horizon should be present
    assert "horizon" in joined.lower()
    assert kw["archetype"] == "founder_ceo"


def test_technova_minors_forces_keyword_for_all():
    cfg = load_company_config(TECHNOVA)
    assert cfg.chatbot_mode is ChatbotMode.keyword
    for emp in cfg.employees:
        assert cfg.effective_chatbot_mode(emp) is ChatbotMode.keyword
