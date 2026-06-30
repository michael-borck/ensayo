"""Phase 3 tests: FastAPI app — UC auth, simulation CRUD, student verify.

Builds are skipped (build=False) so these run without Node.
"""

import pytest
from fastapi.testclient import TestClient

from ensayo.api.app import create_app
from ensayo.api.auth import create_uc

SMALL_YAML = """
company:
  name: "Test Co"
employees:
  - name: "Ada Byron"
    role: "Managing Director"
    archetype: founder_ceo
documents:
  - type: policy
    title: "Security Policy"
    brief: "Access controls."
"""


@pytest.fixture()
def app_ctx(tmp_path, monkeypatch):
    monkeypatch.setenv("ENSAYO_DB", str(tmp_path / "ensayo.db"))
    monkeypatch.setenv("WORKING_CLONES_DIR", str(tmp_path / "sims"))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    app = create_app()
    create_uc(app.state.conn, "uc@example.edu", "pw12345", role="instance_admin")
    client = TestClient(app)
    return client


def _token(client):
    r = client.post("/api/v1/auth/login",
                    json={"email": "uc@example.edu", "password": "pw12345"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(client):
    return {"Authorization": f"Bearer {_token(client)}"}


def test_health(app_ctx):
    r = app_ctx.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_login_bad_password(app_ctx):
    r = app_ctx.post("/api/v1/auth/login",
                     json={"email": "uc@example.edu", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_token(app_ctx):
    assert app_ctx.get("/api/v1/auth/me").status_code == 401
    r = app_ctx.get("/api/v1/auth/me", headers=_auth(app_ctx))
    assert r.status_code == 200 and r.json()["email"] == "uc@example.edu"


def test_create_and_list_simulation(app_ctx):
    r = app_ctx.post("/api/v1/simulations", headers=_auth(app_ctx),
                     json={"name": "Test Co Sim", "company_yaml": SMALL_YAML, "build": False})
    assert r.status_code == 201, r.text
    sim = r.json()
    assert sim["slug"] == "test-co"
    assert sim["site_url"] == f"/sims/{sim['owner_slug']}/{sim['slug']}/"
    assert sim["owner_slug"] == "uc"  # derived from uc@example.edu

    lst = app_ctx.get("/api/v1/simulations", headers=_auth(app_ctx)).json()
    assert len(lst) == 1 and lst[0]["slug"] == "test-co"

    one = app_ctx.get(f"/api/v1/simulations/{sim['id']}", headers=_auth(app_ctx))
    assert one.status_code == 200 and one.json()["name"] == "Test Co Sim"


def test_create_requires_auth(app_ctx):
    r = app_ctx.post("/api/v1/simulations",
                     json={"name": "X", "company_yaml": SMALL_YAML, "build": False})
    assert r.status_code == 401


def test_duplicate_slug_rejected(app_ctx):
    body = {"name": "Test Co Sim", "company_yaml": SMALL_YAML, "build": False}
    assert app_ctx.post("/api/v1/simulations", headers=_auth(app_ctx), json=body).status_code == 201
    assert app_ctx.post("/api/v1/simulations", headers=_auth(app_ctx), json=body).status_code == 400


def test_invalid_yaml_rejected(app_ctx):
    r = app_ctx.post("/api/v1/simulations", headers=_auth(app_ctx),
                     json={"name": "Bad", "company_yaml": "not: [valid", "build": False})
    assert r.status_code == 422


def test_student_shared_password_verify(app_ctx):
    app_ctx.post("/api/v1/simulations", headers=_auth(app_ctx),
                 json={"name": "Test Co Sim", "company_yaml": SMALL_YAML,
                       "shared_password": "letmein", "build": False})
    ok = app_ctx.post("/api/v1/auth/student/verify",
                      json={"slug": "test-co", "password": "letmein"})
    assert ok.status_code == 200 and ok.json()["ok"] is True
    bad = app_ctx.post("/api/v1/auth/student/verify",
                       json={"slug": "test-co", "password": "nope"})
    assert bad.json()["ok"] is False



ACME_YAML = """
company:
  name: "Acme Corp"
employees:
  - name: "Test Person"
"""


def test_two_owners_same_slug(client):
    """Account-scoped slugs: two owners can have the same sim slug."""
    create_uc(client.app.state.conn, "alice@uni.edu", "pw12345")
    create_uc(client.app.state.conn, "bob@uni.edu", "pw12345")
    auth_a = {"Authorization": "Bearer " + client.post(
        "/api/v1/auth/login", json={"email": "alice@uni.edu", "password": "pw12345"}).json()["token"]}
    auth_b = {"Authorization": "Bearer " + client.post(
        "/api/v1/auth/login", json={"email": "bob@uni.edu", "password": "pw12345"}).json()["token"]}

    sim_a = client.post("/api/v1/simulations", headers=auth_a,
                        json={"name": "Alice's Acme", "company_yaml": ACME_YAML, "build": False}).json()
    sim_b = client.post("/api/v1/simulations", headers=auth_b,
                        json={"name": "Bob's Acme", "company_yaml": ACME_YAML, "build": False}).json()

    # Both succeed — same slug, different owners
    assert sim_a["slug"] == "acme-corp"
    assert sim_b["slug"] == "acme-corp"
    assert sim_a["owner_slug"] == "alice"
    assert sim_b["owner_slug"] == "bob"
    assert sim_a["site_url"] == "/sims/alice/acme-corp/"
    assert sim_b["site_url"] == "/sims/bob/acme-corp/"

    # Same owner can't duplicate
    dup = client.post("/api/v1/simulations", headers=auth_a,
                      json={"name": "Another", "company_yaml": ACME_YAML, "build": False})
    assert dup.status_code == 400

    # Student endpoint resolves by owner+slug
    emps = client.get("/api/v1/sims/alice/acme-corp/employees").json()
    assert len(emps) == 1 and emps[0]["name"] == "Test Person"
    emps_b = client.get("/api/v1/sims/bob/acme-corp/employees").json()
    assert len(emps_b) == 1 and emps_b[0]["name"] == "Test Person"

    # Old pattern still works (backward compat — unique slug)
    emps_old = client.get("/api/v1/sims/acme-corp/employees")
    # Ambiguous now (two sims with same slug) — but {slug:path} resolves first match
    assert emps_old.status_code == 200