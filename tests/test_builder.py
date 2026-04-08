"""Integration tests for the site builder."""

from pathlib import Path

from ensayo.builder import build_site

FIXTURES = Path(__file__).parent / "fixtures"


def test_build_produces_expected_files(tmp_path: Path) -> None:
    output = tmp_path / "dist"
    build_site(FIXTURES / "site.yaml", FIXTURES / "content", output)

    # Root pages
    assert (output / "index.html").is_file()
    assert (output / "about.html").is_file()
    assert (output / "services.html").is_file()
    assert (output / "contact.html").is_file()

    # Staff directory
    assert (output / "chatbots" / "index.html").is_file()

    # Employee chatbot page
    assert (output / "chatbots" / "jane-doe" / "index.html").is_file()
    assert (output / "chatbots" / "jane-doe" / "prompt.txt").is_file()

    # Document pages
    assert (output / "docs" / "support" / "index.html").is_file()
    assert (output / "docs" / "support" / "operations-guide.html").is_file()
    assert (output / "docs" / "policy" / "index.html").is_file()
    assert (output / "docs" / "policy" / "privacy-policy.html").is_file()

    # Assets
    assert (output / "assets" / "css" / "style.css").is_file()
    assert (output / "assets" / "js" / "chatbot-keyword.js").is_file()


def test_build_html_contains_company_name(tmp_path: Path) -> None:
    output = tmp_path / "dist"
    build_site(FIXTURES / "site.yaml", FIXTURES / "content", output)

    index_html = (output / "index.html").read_text()
    assert "Test Company" in index_html
    assert "Testing simulations" in index_html


def test_build_employee_page_has_details(tmp_path: Path) -> None:
    output = tmp_path / "dist"
    build_site(FIXTURES / "site.yaml", FIXTURES / "content", output)

    emp_html = (output / "chatbots" / "jane-doe" / "index.html").read_text()
    assert "Jane Doe" in emp_html
    assert "Managing Director" in emp_html
    assert "Decisive" in emp_html
    assert "John Smith" in emp_html


def test_build_doc_page_has_content(tmp_path: Path) -> None:
    output = tmp_path / "dist"
    build_site(FIXTURES / "site.yaml", FIXTURES / "content", output)

    doc_html = (output / "docs" / "support" / "operations-guide.html").read_text()
    assert "Operations Guide" in doc_html
    assert "Client onboarding" in doc_html


def test_build_page_override(tmp_path: Path) -> None:
    output = tmp_path / "dist"
    build_site(FIXTURES / "site.yaml", FIXTURES / "content", output)

    about_html = (output / "about.html").read_text()
    assert "founded in 2015" in about_html


def test_build_css_has_branding(tmp_path: Path) -> None:
    output = tmp_path / "dist"
    build_site(FIXTURES / "site.yaml", FIXTURES / "content", output)

    css = (output / "assets" / "css" / "style.css").read_text()
    assert "#ff0000" in css  # primary override from site.yaml
