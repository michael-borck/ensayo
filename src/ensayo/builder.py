"""Site builder — reads config + content, produces vanilla HTML site."""

from __future__ import annotations

import importlib.resources
import shutil
from pathlib import Path

import markdown as md  # type: ignore[import-untyped]
from jinja2 import Environment, FileSystemLoader
from rich.console import Console

from ensayo.content import load_content, load_site_config
from ensayo.models import Document, SiteConfig, SiteContent

console = Console()


def _get_package_path(subdir: str) -> Path:
    """Get the path to a package data directory."""
    return Path(str(importlib.resources.files("ensayo") / subdir))


def _md_to_html(text: str) -> str:
    """Convert markdown text to HTML."""
    result: str = md.markdown(text, extensions=["tables", "fenced_code"])
    return result


def _resolve_theme_css(theme_name: str) -> str:
    """Load base CSS + theme CSS, return combined stylesheet."""
    themes_dir = _get_package_path("themes")
    base_path = themes_dir / "base.css"
    theme_path = themes_dir / f"{theme_name}.css"

    css_parts: list[str] = []
    if base_path.is_file():
        css_parts.append(base_path.read_text(encoding="utf-8"))
    if theme_path.is_file() and theme_name != "base":
        css_parts.append(theme_path.read_text(encoding="utf-8"))

    return "\n\n".join(css_parts)


def _inject_branding(css: str, config: SiteConfig) -> str:
    """Inject branding color overrides into CSS."""
    b = config.branding
    overrides = f"""
/* Branding overrides from site.yaml */
:root {{
    --sim-primary: {b.primary};
    --sim-secondary: {b.secondary};
    --sim-accent: {b.accent};
    --sim-bg: {b.background};
    --sim-text: {b.text};
}}
"""
    return css + "\n" + overrides


def _compute_base_url(depth: int) -> str:
    """Compute relative base URL for a given nesting depth from site root."""
    if depth == 0:
        return ""
    return "../" * depth


def _render_page(
    env: Environment,
    template_name: str,
    output_path: Path,
    *,
    depth: int = 0,
    **context: object,
) -> None:
    """Render a Jinja2 template and write to output path."""
    template = env.get_template(template_name)
    html = template.render(base_url=_compute_base_url(depth), **context)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def build_site(
    config_path: Path,
    content_dir: Path,
    output_dir: Path,
) -> None:
    """Build a complete vanilla HTML site from config and content."""
    config = load_site_config(config_path)
    content = load_content(content_dir)

    console.print(f"[bold]Building site:[/bold] {config.company.name}")
    console.print(f"  Theme: {config.theme}")
    console.print(f"  Employees: {len(content.employees)}")
    console.print(
        f"  Documents: {len(content.support_docs)} support, {len(content.policy_docs)} policies"
    )
    console.print(f"  Job postings: {len(content.job_postings)}")

    # Set up Jinja2
    templates_dir = _get_package_path("templates")
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=False,
    )

    # Prepare output directory
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Common template context
    ctx = {"site": config, "content": content}

    # --- Root pages ---
    for page_name, template_name, active in [
        ("index", "index.html.j2", "index"),
        ("about", "about.html.j2", "about"),
        ("services", "services.html.j2", "services"),
        ("contact", "contact.html.j2", "contact"),
    ]:
        page_body = ""
        if page_name in content.page_overrides:
            page_body = _md_to_html(content.page_overrides[page_name].body)

        _render_page(
            env, template_name, output_dir / f"{page_name}.html",
            depth=0, active_page=active, page_body=page_body, **ctx,
        )

    # --- Staff directory ---
    _render_page(
        env, "team.html.j2", output_dir / "chatbots" / "index.html",
        depth=1, active_page="team", **ctx,
    )

    # --- Per-employee chatbot pages ---
    for emp in content.employees:
        emp_dir = output_dir / "chatbots" / emp.slug
        _render_page(
            env, "chatbot.html.j2", emp_dir / "index.html",
            depth=2, active_page="team", employee=emp, **ctx,
        )
        # Copy prompt.txt if backstory exists
        if emp.body:
            (emp_dir / "prompt.txt").write_text(emp.body, encoding="utf-8")

    # --- Careers section ---
    if content.job_postings:
        careers_body = ""
        if "careers" in content.page_overrides:
            careers_body = _md_to_html(content.page_overrides["careers"].body)

        _render_page(
            env, "careers.html.j2", output_dir / "careers" / "index.html",
            depth=1, active_page="careers",
            job_postings=content.job_postings, page_body=careers_body, **ctx,
        )

        for job in content.job_postings:
            job_body = _md_to_html(job.body)
            _render_page(
                env, "job.html.j2", output_dir / "careers" / f"{job.slug}.html",
                depth=1, active_page="careers", job=job, job_body=job_body, **ctx,
            )

    # --- Document listing + individual pages ---
    _build_doc_section(
        env, config, content, content.support_docs,
        "Support Documents", "support", output_dir,
    )
    _build_doc_section(
        env, config, content, content.policy_docs,
        "Policies", "policy", output_dir,
    )

    # --- CSS ---
    css_dir = output_dir / "assets" / "css"
    css_dir.mkdir(parents=True, exist_ok=True)
    css = _resolve_theme_css(config.theme)
    css = _inject_branding(css, config)
    (css_dir / "style.css").write_text(css, encoding="utf-8")

    # --- JS ---
    static_js = _get_package_path("static") / "js"
    js_dir = output_dir / "assets" / "js"
    if static_js.is_dir():
        shutil.copytree(str(static_js), str(js_dir))

    # --- Data files ---
    data_src = content_dir / "data"
    if data_src.is_dir():
        shutil.copytree(str(data_src), str(output_dir / "data"))

    # --- Assets (images etc.) ---
    assets_src = content_dir / "assets"
    if assets_src.is_dir():
        assets_dst = output_dir / "assets" / "images"
        shutil.copytree(str(assets_src), str(assets_dst), dirs_exist_ok=True)

    console.print(f"[green bold]Built site → {output_dir}[/green bold]")


def _build_doc_section(
    env: Environment,
    config: SiteConfig,
    content: SiteContent,
    documents: list[Document],
    listing_title: str,
    category: str,
    output_dir: Path,
) -> None:
    """Build a document listing page and individual document pages."""
    docs_dir = output_dir / "docs" / category

    # Listing page
    _render_page(
        env, "doc-listing.html.j2", docs_dir / "index.html",
        depth=2, active_page="docs",
        site=config, content=content,
        documents=documents, listing_title=listing_title,
    )

    # Individual pages
    for doc in documents:
        doc_body = _md_to_html(doc.body)
        _render_page(
            env, "doc.html.j2", docs_dir / f"{doc.slug}.html",
            depth=2, active_page="docs",
            site=config, content=content,
            doc=doc, doc_body=doc_body,
        )
