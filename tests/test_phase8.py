"""Phase 8 (increment 1) tests: multi-site config + generation."""

from pathlib import Path

import pytest

from ensayo.config import ConfigError, is_multisite, load_simulation_config
from ensayo.generator import generate_multisite
from ensayo.models import SimulationConfig

REPO = Path(__file__).resolve().parents[1]
SIM = REPO / "examples" / "workready-mini" / "simulation.yaml"
COMPANY = REPO / "examples" / "nexuspoint" / "company.yaml"


def test_load_simulation_config():
    sim = load_simulation_config(SIM)
    assert sim.name.startswith("WorkReady")
    assert sim.slug == "workready-mini"
    assert [c.slug for c in sim.companies] == ["nexuspoint-systems", "southern-cross-financial"]
    assert sim.workflow == "internship"


def test_is_multisite_detection():
    assert is_multisite(SIM) is True
    assert is_multisite(COMPANY) is False


def test_simulation_rejects_minors():
    with pytest.raises(Exception):
        SimulationConfig.model_validate({
            "name": "X", "audience": "minors",
            "companies": [{"company": {"name": "A Co"}}]})


def test_simulation_requires_companies():
    with pytest.raises(Exception):
        SimulationConfig.model_validate({"name": "X", "companies": []})


def test_duplicate_company_slug_rejected():
    with pytest.raises(Exception):
        SimulationConfig.model_validate({
            "name": "X",
            "companies": [{"company": {"name": "Dup Co"}}, {"company": {"name": "Dup Co"}}]})


def test_generate_multisite_no_build(tmp_path):
    result = generate_multisite(SIM, tmp_path / "out", build=False)
    out = result.output_dir
    # input copied + canonical content per company
    assert (out / "simulation.yaml").exists()
    assert (out / "companies" / "nexuspoint-systems" / "content" / "employees"
            / "alex-nguyen-prompt.txt").exists()
    assert (out / "companies" / "southern-cross-financial" / "content" / "employees"
            / "raj-patel-prompt.txt").exists()
    # portal index links to each company subpath
    portal = (out / "dist" / "index.html").read_text()
    assert "/nexuspoint-systems/" in portal
    assert "/southern-cross-financial/" in portal
    assert "WorkReady Internships" in portal
    assert len(result.company_results) == 2
