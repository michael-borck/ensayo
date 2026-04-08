"""Tests for content loader."""

from pathlib import Path

from ensayo.content import load_content, load_employees, load_site_config

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_site_config() -> None:
    config = load_site_config(FIXTURES / "site.yaml")
    assert config.company.name == "Test Company"
    assert config.company.slug == "test-company"
    assert config.theme == "base"
    assert config.branding.primary == "#ff0000"
    assert config.chatbot.mode == "keyword"
    assert config.chatbot.booking_enabled is False


def test_load_employees() -> None:
    employees = load_employees(FIXTURES / "content")
    assert len(employees) == 1
    emp = employees[0]
    assert emp.name == "Jane Doe"
    assert emp.slug == "jane-doe"
    assert emp.role == "Managing Director"
    assert emp.tier == "executive"
    assert "Decisive" in emp.personality
    assert emp.refers_to["finance"] == "John Smith"
    assert "founded Test Company" in emp.body


def test_load_content_full() -> None:
    content = load_content(FIXTURES / "content")
    assert len(content.employees) == 1
    assert len(content.support_docs) == 1
    assert len(content.policy_docs) == 1
    assert content.support_docs[0].title == "Operations Guide"
    assert content.policy_docs[0].title == "Privacy Policy"
    assert "about" in content.page_overrides
    assert "founded in 2015" in content.page_overrides["about"].body


def test_load_empty_dir(tmp_path: Path) -> None:
    content = load_content(tmp_path)
    assert content.employees == []
    assert content.support_docs == []
    assert content.policy_docs == []
