"""Load site configuration and content from the filesystem."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ensayo.frontmatter import load_frontmatter_file
from ensayo.models import (
    AssetsConfig,
    BrandingConfig,
    CareersConfig,
    ChatbotConfig,
    CompanyConfig,
    Document,
    Employee,
    JobPosting,
    PageOverride,
    SiteConfig,
    SiteContent,
)


def load_site_config(path: Path) -> SiteConfig:
    """Load and parse site.yaml into a SiteConfig."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"site.yaml must be a YAML mapping, got {type(raw).__name__}"
        raise ValueError(msg)

    company_raw = raw.get("company", {})
    company = CompanyConfig(
        name=company_raw.get("name", ""),
        slug=company_raw.get("slug", ""),
        tagline=company_raw.get("tagline", ""),
    )

    branding_raw = raw.get("branding", {})
    branding = BrandingConfig(**{k: v for k, v in branding_raw.items() if v is not None})

    chatbot_raw = raw.get("chatbot", {})
    chatbot = ChatbotConfig(
        mode=chatbot_raw.get("mode", "llm"),
        platform=chatbot_raw.get("platform", "anythingllm"),
        booking_enabled=chatbot_raw.get("booking_enabled", False),
        booking_api=chatbot_raw.get("booking_api", ""),
    )

    careers_raw = raw.get("careers", {})
    careers = CareersConfig(
        label=careers_raw.get("label", "Careers"),
        submit_url=careers_raw.get("submit_url", ""),
        show_apply_form=careers_raw.get("show_apply_form", True),
    )

    assets_raw = raw.get("assets", {})
    assets = AssetsConfig(
        logo=assets_raw.get("logo", ""),
        hero_image=assets_raw.get("hero_image", ""),
        favicon=assets_raw.get("favicon", ""),
    )

    return SiteConfig(
        company=company,
        theme=raw.get("theme", "base"),
        layout=raw.get("layout", ""),
        branding=branding,
        chatbot=chatbot,
        careers=careers,
        assets=assets,
    )


def _make_slug(name: str) -> str:
    """Generate a URL-friendly slug from a name."""
    return name.lower().replace(" ", "-").replace("_", "-")


def _build_employee(meta: dict[str, Any], body: str, slug_from_file: str) -> Employee:
    """Build an Employee from parsed frontmatter and body."""
    return Employee(
        name=meta.get("name", ""),
        slug=meta.get("slug", slug_from_file),
        role=meta.get("role", ""),
        body=body,
        tier=meta.get("tier", "specialist"),
        personality=meta.get("personality", []),
        knowledge=meta.get("knowledge", []),
        refers_to=meta.get("refers_to", {}),
        prompt_extras=meta.get("prompt_extras", ""),
    )


def _build_document(
    meta: dict[str, Any], body: str, slug_from_file: str, category: str
) -> Document:
    """Build a Document from parsed frontmatter and body."""
    return Document(
        title=meta.get("title", slug_from_file.replace("-", " ").title()),
        slug=meta.get("slug", slug_from_file),
        category=category,  # type: ignore[arg-type]
        body=body,
    )


def load_employees(content_dir: Path) -> list[Employee]:
    """Load all employees from content/employees/*.md."""
    employees_dir = content_dir / "employees"
    if not employees_dir.is_dir():
        return []

    employees: list[Employee] = []
    for path in sorted(employees_dir.glob("*.md")):
        meta, body = load_frontmatter_file(path)
        slug = path.stem
        employees.append(_build_employee(meta, body, slug))

    return employees


def load_documents(content_dir: Path, category: str) -> list[Document]:
    """Load all documents from content/docs/{category}/*.md."""
    docs_dir = content_dir / "docs" / category
    if not docs_dir.is_dir():
        return []

    documents: list[Document] = []
    for path in sorted(docs_dir.glob("*.md")):
        meta, body = load_frontmatter_file(path)
        slug = path.stem
        documents.append(_build_document(meta, body, slug, category))

    return documents


def load_page_overrides(content_dir: Path) -> dict[str, PageOverride]:
    """Load page overrides from content/pages/*.md."""
    pages_dir = content_dir / "pages"
    if not pages_dir.is_dir():
        return {}

    overrides: dict[str, PageOverride] = {}
    for path in sorted(pages_dir.glob("*.md")):
        meta, body = load_frontmatter_file(path)
        slug = path.stem
        overrides[slug] = PageOverride(
            slug=slug,
            title=str(meta.get("title", slug.replace("-", " ").title())),
            body=body,
        )

    return overrides


def _build_job_posting(
    meta: dict[str, Any], body: str, slug_from_file: str,
) -> JobPosting:
    """Build a JobPosting from parsed frontmatter and body."""
    return JobPosting(
        title=meta.get("title", slug_from_file.replace("-", " ").title()),
        slug=meta.get("slug", slug_from_file),
        department=meta.get("department", ""),
        location=meta.get("location", ""),
        employment_type=meta.get("employment_type", "Full-time"),
        body=body,
    )


def load_job_postings(content_dir: Path) -> list[JobPosting]:
    """Load all job postings from content/jobs/*.md."""
    jobs_dir = content_dir / "jobs"
    if not jobs_dir.is_dir():
        return []

    postings: list[JobPosting] = []
    for path in sorted(jobs_dir.glob("*.md")):
        meta, body = load_frontmatter_file(path)
        slug = path.stem
        postings.append(_build_job_posting(meta, body, slug))

    return postings


def load_data_files(content_dir: Path) -> list[Path]:
    """List data files from content/data/."""
    data_dir = content_dir / "data"
    if not data_dir.is_dir():
        return []
    return sorted(data_dir.iterdir())


def load_content(content_dir: Path) -> SiteContent:
    """Load all content from the content/ directory."""
    return SiteContent(
        employees=load_employees(content_dir),
        support_docs=load_documents(content_dir, "support"),
        policy_docs=load_documents(content_dir, "policy"),
        page_overrides=load_page_overrides(content_dir),
        data_files=load_data_files(content_dir),
        job_postings=load_job_postings(content_dir),
    )
