"""Phase 2 tests: content libraries and LLM-assisted bulk generation (stub path)."""

from pathlib import Path

from ensayo.config import dump_config_yaml, load_company_config
from ensayo.enrich import enrich_config, estimate
from ensayo.library import (
    list_industries,
    load_document_template,
    load_scenario_template,
)
from ensayo.llm import ProviderSpec, StubProvider, resolve_spec
from ensayo.models import CompanyConfig

REPO = Path(__file__).resolve().parents[1]
SPARSE = REPO / "examples" / "sparse" / "company.yaml"

STUB = StubProvider()
STUB_SPEC = ProviderSpec(provider="stub")


def test_industry_library_has_six_plus():
    assert len(list_industries()) >= 6


def test_scenario_templates_load():
    growth = load_scenario_template("growth")
    assert growth is not None and growth.prompt_hint
    assert load_scenario_template("nonexistent") is None


def test_document_template_falls_back_to_custom():
    assert load_document_template("policy").type == "policy"
    assert load_document_template("nope").type == "custom"


def test_resolve_spec_defaults_to_stub(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    spec = resolve_spec(None)
    assert spec.provider == "stub"


def test_resolve_spec_reads_config_llm(monkeypatch):
    monkeypatch.setenv("MY_KEY", "secret")
    cfg = CompanyConfig.model_validate({
        "company": {"name": "X"},
        "llm": {"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key_env": "MY_KEY"},
    })
    spec = resolve_spec(cfg)
    assert spec.provider == "anthropic"
    assert spec.api_key == "secret"


def test_estimate_counts_sparse_items():
    cfg = load_company_config(SPARSE)
    est = estimate(cfg)
    # 4 employees × (backstory+opinions+perspective) + scenario + 2 docs
    assert est["items"] == 4 * 3 + 1 + 2
    assert est["input_tokens"] > 0 and est["output_tokens"] > 0


def test_enrich_stub_fills_all_content():
    cfg = load_company_config(SPARSE)
    result = enrich_config(cfg, STUB, STUB_SPEC)
    assert result.failed == 0
    assert result.generated == result.items.__len__()
    assert cfg.company.scenario.description.strip()
    for emp in cfg.employees:
        assert emp.customisation.background.strip()
        assert emp.customisation.opinions
        assert emp.customisation.scenario_perspective.strip()
    for doc in cfg.documents:
        assert doc.content.strip()


def test_enrich_skips_existing_unless_forced():
    cfg = load_company_config(SPARSE)
    cfg.employees[0].customisation.background = "Already written."
    before = estimate(cfg)["items"]
    forced = estimate(cfg, force=True)["items"]
    assert before < forced  # one fewer backstory to do when not forcing


def test_enriched_config_serialises_and_reloads(tmp_path):
    cfg = load_company_config(SPARSE)
    enrich_config(cfg, STUB, STUB_SPEC)
    out = tmp_path / "enriched.yaml"
    out.write_text(dump_config_yaml(cfg), encoding="utf-8")
    reloaded = load_company_config(out)
    assert reloaded.company.name == "BriteLeaf Organics"
    assert all(e.customisation.background for e in reloaded.employees)



def test_known_documents_round_trip(tmp_path):
    """known_documents (doc↔persona mapping) survives YAML dump/load."""
    from ensayo.models import Employee, EmployeeCustomisation

    cfg = load_company_config(SPARSE)
    cfg.employees[0].customisation.known_documents = ["Security Policy", "Employee Handbook"]
    out = tmp_path / "mapped.yaml"
    out.write_text(dump_config_yaml(cfg), encoding="utf-8")
    reloaded = load_company_config(out)
    assert reloaded.employees[0].customisation.known_documents == ["Security Policy", "Employee Handbook"]