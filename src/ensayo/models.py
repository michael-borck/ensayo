"""Pydantic models for the ``company.yaml`` simulation configuration.

YAML is canonical for simulation content (spec §3.3). These models are the
single validated representation the generator works from. The schema is a
generalisation of the proven WorkReady ``brief.yaml`` format.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Turn an arbitrary string into a URL-safe slug."""
    return _SLUG_RE.sub("-", value.strip().lower()).strip("-")


class _Model(BaseModel):
    """Base model: ignore unknown keys so the schema can grow forward-compatibly."""

    model_config = ConfigDict(extra="ignore")


class Audience(str, Enum):
    adults = "adults"
    minors = "minors"


class ChatbotMode(str, Enum):
    keyword = "keyword"
    llm = "llm"
    hybrid = "hybrid"


class Tier(str, Enum):
    executive = "executive"
    manager = "manager"
    specialist = "specialist"
    staff = "staff"


class Branding(_Model):
    colors: dict[str, str] = Field(default_factory=dict)
    logo: str | None = None
    font: str | None = None


class Profile(_Model):
    founded: int | None = None
    employees: int | None = None
    revenue: str | None = None
    structure: str | None = None
    description: str = ""
    key_facts: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)


class Scenario(_Model):
    type: str = "custom"
    name: str = ""
    description: str = ""
    key_tensions: list[str] = Field(default_factory=list)


class CompanySection(_Model):
    name: str
    slug: str = ""
    tagline: str = ""
    industry: str = "general"
    location: str = ""
    profile: Profile = Field(default_factory=Profile)
    scenario: Scenario = Field(default_factory=Scenario)

    @model_validator(mode="after")
    def _default_slug(self) -> CompanySection:
        if not self.slug:
            self.slug = slugify(self.name)
        return self


class EmployeeCustomisation(_Model):
    years_at_company: int | None = None
    years_in_industry: int | None = None
    background: str = ""
    prior_experience: list[str] = Field(default_factory=list)
    personality_additions: list[str] = Field(default_factory=list)
    knowledge_additions: list[str] = Field(default_factory=list)
    opinions: list[str] = Field(default_factory=list)
    scenario_perspective: str = ""


class Employee(_Model):
    id: str = ""
    name: str
    role: str = ""
    title: str | None = None
    archetype: str = "staff"
    tier: Tier = Tier.staff
    department: str | None = None
    customisation: EmployeeCustomisation = Field(default_factory=EmployeeCustomisation)
    refers_to: dict[str, str] = Field(default_factory=dict)
    chatbot_mode: ChatbotMode | None = None  # falls back to company default
    chatbot_embed_id: str | None = None  # AnythingLLM embed UUID (set by Phase 4 provisioning)
    avatar: str | None = None

    @model_validator(mode="after")
    def _default_id(self) -> Employee:
        if not self.id:
            self.id = slugify(self.name)
        return self

    @property
    def slug(self) -> str:
        return self.id


class Document(_Model):
    type: str = "custom"
    title: str
    slug: str = ""
    brief: str = ""
    content: str = ""

    @model_validator(mode="after")
    def _default_slug(self) -> Document:
        if not self.slug:
            self.slug = slugify(self.title)
        return self


class Platform(_Model):
    booking_enabled: bool = False
    lecturer_dashboard: bool = False


class AnythingLLM(_Model):
    """Connection details for AnythingLLM embed widgets (full provisioning: Phase 4)."""

    base_url: str = ""  # e.g. https://anythingllm.example.com/api
    embed_src: str = ""  # e.g. https://anythingllm.example.com/embed/anythingllm-chat.min.js


class LLMConfig(_Model):
    """Per-simulation LLM selection for content generation (spec §7.4).

    The API key is *never* stored here — only the name of the env var to read it
    from. Resolution precedence is config > environment > stub (see llm.py).
    """

    provider: str = ""  # stub | ollama | lmstudio | openai | openrouter | gemini | anthropic
    model: str = ""
    base_url: str = ""
    api_key_env: str = ""


class CompanyConfig(_Model):
    """Top-level single-company simulation configuration."""

    company: CompanySection
    audience: Audience = Audience.adults
    theme: str = "tech-modern"
    layout: str = "topnav"
    chatbot_mode: ChatbotMode = ChatbotMode.keyword
    branding: Branding = Field(default_factory=Branding)
    platform: Platform = Field(default_factory=Platform)
    anythingllm: AnythingLLM = Field(default_factory=AnythingLLM)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    employees: list[Employee] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)

    @field_validator("employees")
    @classmethod
    def _unique_employee_ids(cls, employees: list[Employee]) -> list[Employee]:
        seen: set[str] = set()
        for emp in employees:
            eid = emp.id or slugify(emp.name)
            if eid in seen:
                raise ValueError(f"duplicate employee id/slug: {eid!r}")
            seen.add(eid)
        return employees

    @model_validator(mode="after")
    def _enforce_audience_defaults(self) -> CompanyConfig:
        # Minors-safe bundle (spec §7.2): keyword chatbots only.
        if self.audience is Audience.minors:
            self.chatbot_mode = ChatbotMode.keyword
            for emp in self.employees:
                emp.chatbot_mode = ChatbotMode.keyword
        return self

    @property
    def slug(self) -> str:
        return self.company.slug

    def effective_chatbot_mode(self, employee: Employee) -> ChatbotMode:
        return employee.chatbot_mode or self.chatbot_mode
