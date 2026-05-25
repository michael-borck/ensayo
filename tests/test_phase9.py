"""Phase 9 tests: gallery command + documentation presence."""

from pathlib import Path

from click.testing import CliRunner

from ensayo.cli import main

REPO = Path(__file__).resolve().parents[1]


def test_gallery_no_build(tmp_path):
    out = tmp_path / "gallery"
    res = CliRunner().invoke(main, ["gallery", "--no-build", "-o", str(out)])
    assert res.exit_code == 0, res.output
    assert (out / "index.html").exists()
    # content written per company theme (build skipped)
    assert (out / ".work" / "tech-modern" / "company.yaml").exists()
    assert "tech-modern" in (out / "index.html").read_text()


def test_docs_guides_present():
    guides = REPO / "docs" / "guides"
    for name in ["getting-started", "configuration-reference", "deployment",
                 "theme-authoring", "archetype-authoring", "safe-mode"]:
        assert (guides / f"{name}.md").exists(), name
    assert (REPO / "docs" / "security-review.md").exists()
    assert (REPO / "docs" / "accessibility.md").exists()
    assert (REPO / "CHANGELOG.md").exists()
