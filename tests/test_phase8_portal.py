"""Phase 8 increment 4 tests: employees endpoint + student portal serving."""

WF_YAML = """
company:
  name: "Flow Co"
employees:
  - name: "Ada Byron"
    role: "Hiring Manager"
    archetype: founder_ceo
  - name: "Marcus Webb"
    role: "Security Lead"
    archetype: technical_specialist
"""


def _sim(client, auth):
    r = client.post("/api/v1/simulations", headers=auth, json={
        "name": "Flow Sim", "company_yaml": WF_YAML,
        "auth_mode": "individual_account", "workflow": "internship", "build": False})
    assert r.status_code == 201, r.text
    return r.json()


def test_employees_endpoint(client, auth):
    sim = _sim(client, auth)
    emps = client.get(f"/api/v1/sims/{sim['slug']}/employees").json()
    slugs = {e["slug"] for e in emps}
    assert slugs == {"ada-byron", "marcus-webb"}
    assert any(e["role"] == "Hiring Manager" for e in emps)


def test_portal_is_served(client):
    r = client.get("/portal/")
    assert r.status_code == 200
    assert "Student Portal" in r.text
