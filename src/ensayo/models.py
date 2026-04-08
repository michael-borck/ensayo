"""Data models for ensayo configuration and content."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class CompanyConfig:
    """Company metadata from site.yaml."""

    name: str
    slug: str
    tagline: str = ""


@dataclass
class BrandingConfig:
    """Branding overrides from site.yaml."""

    primary: str = "#2563eb"
    secondary: str = "#1e40af"
    accent: str = "#f59e0b"
    background: str = "#f7f8fb"
    text: str = "#222222"


@dataclass
class ChatbotConfig:
    """Chatbot configuration from site.yaml."""

    mode: Literal["llm", "keyword"] = "llm"
    platform: str = "anythingllm"
    booking_enabled: bool = False
    booking_api: str = ""


@dataclass
class SiteConfig:
    """Top-level site configuration from site.yaml."""

    company: CompanyConfig
    theme: str = "base"
    branding: BrandingConfig = field(default_factory=BrandingConfig)
    chatbot: ChatbotConfig = field(default_factory=ChatbotConfig)


@dataclass
class Employee:
    """An employee parsed from content/employees/*.md frontmatter + body."""

    name: str
    slug: str
    role: str
    body: str = ""
    tier: Literal["executive", "manager", "specialist"] = "specialist"
    personality: list[str] = field(default_factory=list)
    knowledge: list[str] = field(default_factory=list)
    refers_to: dict[str, str] = field(default_factory=dict)
    prompt_extras: str = ""


@dataclass
class Document:
    """A document parsed from content/docs/{category}/*.md frontmatter + body."""

    title: str
    slug: str
    category: Literal["support", "policy"]
    body: str = ""


@dataclass
class PageOverride:
    """A page override from content/pages/*.md."""

    slug: str
    title: str
    body: str = ""


@dataclass
class SiteContent:
    """Aggregated content loaded from the content/ directory."""

    employees: list[Employee] = field(default_factory=list)
    support_docs: list[Document] = field(default_factory=list)
    policy_docs: list[Document] = field(default_factory=list)
    page_overrides: dict[str, PageOverride] = field(default_factory=dict)
    data_files: list[Path] = field(default_factory=list)
