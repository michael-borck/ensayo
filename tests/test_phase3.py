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
    assert sim["site_url"] == "/sims/test-co/"

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
