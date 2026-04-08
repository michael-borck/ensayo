"""Tests for the init orchestrator."""

from pathlib import Path
from unittest.mock import patch

FIXTURES = Path(__file__).parent / "fixtures"

MOCK_CONTENT = """---
name: Test Employee
slug: test-employee
role: Director
tier: executive
personality:
  - Decisive
knowledge:
  - Strategy
refers_to: {}
prompt_extras: ""
---

# Test backstory"""


def test_init_generates_content_and_builds(tmp_path: Path) -> None:
    output = tmp_path / "my-sim"

    with patch("ensayo.generator.generate_text", return_value=MOCK_CONTENT):
        from ensayo.generator import generate_all

        content_dir = output / "content"
        generate_all(FIXTURES / "brief.yaml", content_dir)

    # site.yaml should exist
    site_yaml = output / "site.yaml"
    assert site_yaml.is_file()

    # Content should exist
    assert (content_dir / "employees").is_dir()

    # Now build
    from ensayo.builder import build_site

    dist_dir = output / "dist"
    build_site(site_yaml, content_dir, dist_dir)

    # Built site should exist
    assert (dist_dir / "index.html").is_file()
    assert (dist_dir / "assets" / "css" / "style.css").is_file()
