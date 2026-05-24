"""Phase 6 tests: Safe Mode — audience bundle, overrides, mature filtering."""

from ensayo.library import Archetype, filter_mature, list_archetypes
from ensayo.models import Audience, ChatbotMode, CompanyConfig
from ensayo.safemode import MINORS_BUNDLE, audience_report


def _cfg(d: dict) -> CompanyConfig:
    return CompanyConfig.model_validate(d)


# --- bundle + override reporting (model level) ----------------------------

def test_report_adults_is_safe():
    r = audience_report(_cfg({"company": {"name": "X"}}))
    assert r["audience"] == "adults" and r["safe"] and r["overrides"] == []


def test_report_minors_no_overrides_safe():
    r = audience_report(_cfg({"company": {"name": "X"}, "audience": "minors"}))
    assert r["safe"] is True
    assert r["overrides"] == []
    assert len(r["bundle"]) == len(MINORS_BUNDLE)


def test_minors_without_override_forces_keyword():
    c = _cfg({"company": {"name": "X"}, "audience": "minors", "chatbot_mode": "llm",
              "employees": [{"name": "Ada Byron", "chatbot_mode": "llm"}]})
    assert c.chatbot_mode is ChatbotMode.keyword
    assert c.employees[0].chatbot_mode is ChatbotMode.keyword


def test_acknowledged_override_relaxes_and_is_reported():
    c = _cfg({"company": {"name": "X"}, "audience": "minors",
              "audience_overrides": ["llm_chatbots"], "chatbot_mode": "llm",
              "employees": [{"name": "Ada Byron", "chatbot_mode": "llm"}]})
    # override honoured: model did NOT force keyword
    assert c.chatbot_mode is ChatbotMode.llm
    assert c.employees[0].chatbot_mode is ChatbotMode.llm
    r = audience_report(c)
    assert r["safe"] is False
    assert any(o["key"] == "llm_chatbots" for o in r["overrides"])


def test_filter_mature_archetypes():
    items = [Archetype(name="x", mature=True), Archetype(name="y")]
    assert [a.name for a in filter_mature(items)] == ["y"]


def test_list_archetypes_include_mature_param():
    assert len(list_archetypes(include_mature=False)) <= len(list_archetypes())


# --- API ------------------------------------------------------------------

MINORS = """
company:
  name: "Bright Minds Academy"
audience: minors
employees:
  - name: "Ada Byron"
    role: "Teacher"
    archetype: founder_ceo
"""

MINORS_OVERRIDE = """
company:
  name: "Bright Minds Override"
audience: minors
audience_overrides:
  - llm_chatbots
chatbot_mode: llm
employees:
  - name: "Ada Byron"
    role: "Teacher"
    archetype: founder_ceo
    chatbot_mode: llm
"""


def _create(client, auth, yaml, **extra):
    r = client.post("/api/v1/simulations", headers=auth,
                    json={"name": "Sim", "company_yaml": yaml, "build": False, **extra})
    return r


def test_audience_endpoint_safe(client, auth):
    sim = _create(client, auth, MINORS).json()
    rep = client.get(f"/api/v1/simulations/{sim['id']}/audience", headers=auth).json()
    assert rep["audience"] == "minors" and rep["safe"] is True


def test_audience_endpoint_reports_override(client, auth):
    sim = _create(client, auth, MINORS_OVERRIDE).json()
    rep = client.get(f"/api/v1/simulations/{sim['id']}/audience", headers=auth).json()
    assert rep["safe"] is False
    assert any(o["key"] == "llm_chatbots" for o in rep["overrides"])


def test_minors_llm_assist_refused(client, auth):
    r = _create(client, auth, MINORS, with_llm=True)
    assert r.status_code == 400
    assert "minors" in r.json()["detail"].lower()


def test_provision_allowed_with_acknowledged_override(client, auth):
    sim = _create(client, auth, MINORS_OVERRIDE).json()
    r = client.post(f"/api/v1/simulations/{sim['id']}/provision-chatbots",
                    headers=auth, json={"build": False})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "dry-run"
