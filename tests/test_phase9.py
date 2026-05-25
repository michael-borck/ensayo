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


WIZ_CONFIG = {
    "company": {
        "name": "Wizard Co", "tagline": "Built by the wizard", "industry": "general",
        "location": "Perth, WA", "profile": {"description": "A test company."},
        "scenario": {"type": "growth", "name": "The challenge", "description": ""},
    },
    "audience": "adults", "theme": "tech-modern",
    "employees": [{"name": "Ada Byron", "role": "Managing Director", "archetype": "founder_ceo"}],
    "documents": [{"type": "policy", "title": "Security Policy", "brief": "Access controls."}],
}


def test_create_from_structured_config(client, auth):
    """The wizard sends structured fields; the server builds the YAML."""
    r = client.post("/api/v1/simulations", headers=auth, json={
        "name": "Wizard Sim", "config": WIZ_CONFIG, "build": False})
    assert r.status_code == 201, r.text
    sim = r.json()
    assert sim["slug"] == "wizard-co"
    yaml_text = client.get(f"/api/v1/simulations/{sim['id']}/yaml",
                           headers=auth).json()["company_yaml"]
    assert "Wizard Co" in yaml_text and "Ada Byron" in yaml_text


def test_create_requires_config_or_yaml(client, auth):
    r = client.post("/api/v1/simulations", headers=auth, json={"name": "X", "build": False})
    assert r.status_code == 422


def test_wizard_catalog_endpoints(client, auth):
    themes = client.get("/api/v1/themes", headers=auth).json()
    assert any(t["name"] == "tech-modern" for t in themes)
    assert not any(t["name"] in ("portal-clean", "directory") for t in themes)
    archetypes = client.get("/api/v1/archetypes", headers=auth).json()
    assert any(a["name"] == "founder_ceo" for a in archetypes)
    workflows = client.get("/api/v1/workflows", headers=auth).json()
    assert {"internship", "medical_network"} <= {w["name"] for w in workflows}


def test_create_with_workflow(client, auth):
    """The wizard sends a chosen workflow; it's stored on the simulation."""
    r = client.post("/api/v1/simulations", headers=auth, json={
        "name": "Workflow Sim", "config": WIZ_CONFIG, "auth_mode": "individual_account",
        "workflow": "internship", "build": False})
    assert r.status_code == 201, r.text
    assert r.json()["workflow"] == "internship"


def test_docs_guides_present():
    guides = REPO / "docs" / "guides"
    for name in ["getting-started", "configuration-reference", "deployment",
                 "theme-authoring", "archetype-authoring", "safe-mode"]:
        assert (guides / f"{name}.md").exists(), name
    assert (REPO / "docs" / "security-review.md").exists()
    assert (REPO / "docs" / "accessibility.md").exists()
    assert (REPO / "CHANGELOG.md").exists()
