"""Phase 0 foundation tests: config validation, content generation, audience rules."""

from pathlib import Path

import pytest

from ensayo.config import ConfigError, load_company_config
from ensayo.generator import generate
from ensayo.models import Audience, ChatbotMode, CompanyConfig
from ensayo.prompts import build_keyword_responses, build_prompt

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "nexuspoint" / "company.yaml"


def test_load_example_config():
    cfg = load_company_config(EXAMPLE)
    assert cfg.company.name == "NexusPoint Systems"
    assert cfg.company.slug == "nexuspoint-systems"
    assert len(cfg.employees) == 7
    assert len(cfg.documents) == 5


def test_slugs_default_from_names():
    cfg = CompanyConfig.model_validate({
        "company": {"name": "Acme Cloud Co"},
        "employees": [{"name": "Dana Lee", "role": "CEO"}],
    })
    assert cfg.company.slug == "acme-cloud-co"
    assert cfg.employees[0].slug == "dana-lee"


def test_duplicate_employee_ids_rejected():
    with pytest.raises(Exception):
        CompanyConfig.model_validate({
            "company": {"name": "X"},
            "employees": [{"name": "Sam Roe"}, {"name": "Sam Roe"}],
        })


def test_minors_audience_forces_keyword_chatbots():
    cfg = CompanyConfig.model_validate({
        "company": {"name": "School Co"},
        "audience": "minors",
        "chatbot_mode": "llm",
        "employees": [{"name": "Pat Kim", "chatbot_mode": "llm"}],
    })
    assert cfg.audience is Audience.minors
    assert cfg.chatbot_mode is ChatbotMode.keyword
    assert cfg.effective_chatbot_mode(cfg.employees[0]) is ChatbotMode.keyword


def test_missing_config_file():
    with pytest.raises(ConfigError):
        load_company_config(REPO / "does-not-exist.yaml")


def test_prompt_includes_persona_details():
    cfg = load_company_config(EXAMPLE)
    marcus = next(e for e in cfg.employees if e.slug == "marcus-webb")
    prompt = build_prompt(cfg, marcus)
    assert "Marcus Webb" in prompt
    assert "Cybersecurity Lead" in prompt
    assert "NexusPoint Systems" in prompt
    assert "Stay in character" in prompt


def test_keyword_responses_have_greeting_and_rules():
    cfg = load_company_config(EXAMPLE)
    alex = next(e for e in cfg.employees if e.slug == "alex-nguyen")
    kw = build_keyword_responses(cfg, alex)
    assert "Alex Nguyen" in kw["greeting"]
    assert kw["rules"]
    assert "fallback" in kw


def test_generate_no_build_writes_canonical_content(tmp_path):
    result = generate(EXAMPLE, tmp_path / "out", build=False)
    out = result.output_dir
    assert (out / "company.yaml").exists()
    assert (out / "content" / "employees" / "marcus-webb-prompt.txt").exists()
    assert (out / "content" / "employees" / "marcus-webb.md").exists()
    assert (out / "content" / "docs" / "information-security-policy.md").exists()
    assert result.content_manifest == {"employees": 7, "documents": 5}
    assert result.built is False
