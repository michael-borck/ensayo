"""Phase 4 tests: AnythingLLM provisioning (dry-run mode, no live instance)."""

from ensayo.api.anythingllm import AnythingLLMClient
from ensayo.content import _company_payload, _employee_payload
from ensayo.models import CompanyConfig

YAML_TWO = """
company:
  name: "Chatbot Co"
employees:
  - name: "Ada Byron"
    role: "Managing Director"
    archetype: founder_ceo
  - name: "Alan Turing"
    role: "Technical Lead"
    archetype: technical_specialist
"""

YAML_MINORS = """
company:
  name: "School Co"
audience: minors
employees:
  - name: "Pat Kim"
    role: "Teacher"
    archetype: staff
"""


def _create(client, auth, yaml, name="Sim"):
    r = client.post("/api/v1/simulations", headers=auth,
                    json={"name": name, "company_yaml": yaml, "build": False})
    assert r.status_code == 201, r.text
    return r.json()


def test_client_dry_run_when_unconfigured(monkeypatch):
    monkeypatch.delenv("ANYTHINGLLM_URL", raising=False)
    monkeypatch.delenv("ANYTHINGLLM_API_KEY", raising=False)
    c = AnythingLLMClient.from_env()
    assert c.configured is False
    assert c.embed_base_url() == "about:dryrun"


def test_provision_dry_run(client, auth):
    sim = _create(client, auth, YAML_TWO, "Chatbot Sim")
    r = client.post(f"/api/v1/simulations/{sim['id']}/provision-chatbots",
                    headers=auth, json={"build": False})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mode"] == "dry-run"
    assert data["provisioned"] == 2
    assert data["failed"] == 0

    # embed ids + llm mode written back into the config
    cfg = client.get(f"/api/v1/simulations/{sim['id']}", headers=auth).json()["config_cache"]
    emps = {e["id"]: e for e in cfg["employees"]}
    assert emps["ada-byron"]["chatbot_embed_id"].startswith("dryrun-")
    assert emps["ada-byron"]["chatbot_mode"] == "llm"
    assert cfg["anythingllm"]["base_url"] == "about:dryrun"


def test_booking_gate_flags_in_payloads():
    cfg = CompanyConfig.model_validate({
        "company": {"name": "Gated Co"},
        "api_base_url": "https://api.example.edu",
        "platform": {"booking_enabled": True, "chatbot_requires_booking": True},
        "employees": [{"name": "Ada Byron", "role": "MD", "archetype": "founder_ceo"}],
    })
    assert _company_payload(cfg)["apiBaseUrl"] == "https://api.example.edu"
    assert _employee_payload(cfg, cfg.employees[0])["requiresBooking"] is True


def test_booking_gate_off_when_booking_disabled():
    cfg = CompanyConfig.model_validate({
        "company": {"name": "Co"},
        "platform": {"chatbot_requires_booking": True},  # but booking_enabled False
        "employees": [{"name": "Ada Byron", "archetype": "staff"}],
    })
    assert _employee_payload(cfg, cfg.employees[0])["requiresBooking"] is False


def test_provision_refused_for_minors(client, auth):
    sim = _create(client, auth, YAML_MINORS, "School Sim")
    r = client.post(f"/api/v1/simulations/{sim['id']}/provision-chatbots",
                    headers=auth, json={"build": False})
    assert r.status_code == 400
    assert "minors" in r.json()["detail"].lower()


YAML_DOC_MAP = """
company:
  name: "Doc Mapping Co"
documents:
  - title: "Security Policy"
    type: policy
    content: "Use 2FA everywhere."
  - title: "Employee Handbook"
    type: internal
    content: "Be excellent to each other."
employees:
  - name: "Targeted Ted"
    role: "Analyst"
    customisation:
      background: "Ted worked at the NSA for 10 years."
      known_documents: ["Security Policy"]
  - name: "General Gwen"
    role: "Manager"
"""


def test_provision_per_persona_doc_targeting(client, auth):
    """known_documents limits docs per persona; backstory counts as +1."""
    sim = _create(client, auth, YAML_DOC_MAP, "Doc Mapping Sim")
    logs: list[str] = []
    conn = client.app.state.conn
    sim_row = conn.execute(
        "SELECT * FROM simulations WHERE id = ?", (sim["id"],)).fetchone()
    from ensayo.api.provision import provision_chatbots
    provision_chatbots(conn, sim_row, build=False, log=logs.append)

    ted = [l for l in logs if "Ted" in l]
    gwen = [l for l in logs if "Gwen" in l]
    assert ted, f"no log for Ted in {logs}"
    assert gwen, f"no log for Gwen in {logs}"
    # Ted: 1 known doc (Security Policy) + 1 backstory = 2
    assert "2 docs" in ted[0], ted[0]
    # Gwen: no known_documents → all docs (2), no backstory = 2
    assert "2 docs" in gwen[0], gwen[0]


def test_provision_known_documents_persists(client, auth):
    """known_documents survives provisioning round-trip in config_cache."""
    sim = _create(client, auth, YAML_DOC_MAP, "Persist Sim")
    r = client.post(f"/api/v1/simulations/{sim['id']}/provision-chatbots",
                    headers=auth, json={"build": False})
    assert r.status_code == 200, r.text
    cfg = client.get(f"/api/v1/simulations/{sim['id']}", headers=auth).json()["config_cache"]
    ted = next(e for e in cfg["employees"] if e["id"] == "targeted-ted")
    assert ted["customisation"]["known_documents"] == ["Security Policy"]


def test_keyword_rules_include_known_documents():
    """build_keyword_responses adds a rule for each known document."""
    from ensayo.prompts import build_keyword_responses
    cfg = CompanyConfig.model_validate({
        "company": {"name": "Test Co"},
        "documents": [{"title": "Security Policy", "type": "policy"}],
        "employees": [{"name": "Ada Byron", "role": "CTO", "customisation": {
            "known_documents": ["Security Policy"]}}],
    })
    kw = build_keyword_responses(cfg, cfg.employees[0])
    doc_rules = [r for r in kw["rules"] if "Security Policy" in r["response"]]
    assert doc_rules, f"no keyword rule for known document in {kw['rules']}"
    assert "Documents section" in doc_rules[0]["response"]


def test_employee_payload_includes_known_documents():
    """_employee_payload outputs knownDocuments with title + slug for linking."""
    cfg = CompanyConfig.model_validate({
        "company": {"name": "Test Co"},
        "documents": [
            {"title": "Security Policy", "type": "policy"},
            {"title": "Employee Handbook", "type": "internal"},
        ],
        "employees": [{"name": "Ada Byron", "role": "CTO", "customisation": {
            "known_documents": ["Security Policy", "Employee Handbook", "Missing Doc"]}}],
    })
    payload = _employee_payload(cfg, cfg.employees[0])
    docs = payload["knownDocuments"]
    assert len(docs) == 2  # "Missing Doc" filtered out (not in config.documents)
    assert {"title": "Security Policy", "slug": "security-policy"} in docs
    assert {"title": "Employee Handbook", "slug": "employee-handbook"} in docs


def test_employee_payload_known_documents_empty_by_default():
    """No known_documents → empty list (backward compatible)."""
    cfg = CompanyConfig.model_validate({
        "company": {"name": "Test Co"},
        "employees": [{"name": "Ada Byron"}],
    })
    assert _employee_payload(cfg, cfg.employees[0])["knownDocuments"] == []


def test_api_base_url_round_trips(client, auth):
    """api_base_url survives create → config retrieval."""
    yaml = """
company:
  name: "Booking Co"
api_base_url: "https://ensayo.locoensayo.org"
platform:
  booking_enabled: true
  chatbot_requires_booking: true
employees:
  - name: "Ada Byron"
    role: "CEO"
"""
    sim = _create(client, auth, yaml, "Booking Sim")
    cfg = client.get(f"/api/v1/simulations/{sim['id']}/config", headers=auth).json()
    assert cfg["api_base_url"] == "https://ensayo.locoensayo.org"
    assert cfg["platform"]["booking_enabled"] is True


def test_cors_headers_on_student_endpoints(client):
    """Student-facing endpoints return CORS headers (cross-origin booking API)."""
    # OPTIONS preflight (CORS middleware needs Origin + Access-Control-Request-Method)
    r = client.options("/api/v1/sims/test-slug/availability",
                       headers={"Origin": "https://example.github.io",
                                "Access-Control-Request-Method": "GET"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "*"

    # GET with Origin header (404 is fine — we just want CORS headers present)
    r = client.get("/api/v1/sims/test-slug/availability?employee=x&date=2026-06-30",
                   headers={"Origin": "https://example.github.io"})
    assert r.headers.get("access-control-allow-origin") == "*"