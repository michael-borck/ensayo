"""Tests for data models."""

from ensayo.models import (
    BrandingConfig,
    ChatbotConfig,
    CompanyConfig,
    Employee,
    SiteConfig,
)


def test_site_config_defaults() -> None:
    config = SiteConfig(company=CompanyConfig(name="Test", slug="test"))
    assert config.theme == "base"
    assert config.branding.primary == "#2563eb"
    assert config.chatbot.mode == "llm"
    assert config.chatbot.booking_enabled is False


def test_employee_defaults() -> None:
    emp = Employee(name="Jane", slug="jane", role="Director")
    assert emp.tier == "specialist"
    assert emp.personality == []
    assert emp.refers_to == {}
    assert emp.body == ""


def test_site_config_custom() -> None:
    config = SiteConfig(
        company=CompanyConfig(name="Acme", slug="acme", tagline="We do things"),
        theme="warm-hospitality",
        branding=BrandingConfig(primary="#8B4513"),
        chatbot=ChatbotConfig(mode="keyword", booking_enabled=True),
    )
    assert config.company.tagline == "We do things"
    assert config.branding.primary == "#8B4513"
    assert config.chatbot.mode == "keyword"
