"""Phase 4 tests: AnythingLLM provisioning (dry-run mode, no live instance)."""

from ensayo.api.anythingllm import AnythingLLMClient

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


def test_provision_refused_for_minors(client, auth):
    sim = _create(client, auth, YAML_MINORS, "School Sim")
    r = client.post(f"/api/v1/simulations/{sim['id']}/provision-chatbots",
                    headers=auth, json={"build": False})
    assert r.status_code == 400
    assert "minors" in r.json()["detail"].lower()
