"""Shared fixtures for API tests."""

import pytest
from fastapi.testclient import TestClient

from ensayo.api.app import create_app
from ensayo.api.auth import create_uc


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ENSAYO_DB", str(tmp_path / "ensayo.db"))
    monkeypatch.setenv("WORKING_CLONES_DIR", str(tmp_path / "sims"))
    monkeypatch.setenv("JWT_SECRET", "test-secret-32-bytes-xxxxxxxxxxxx")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    app = create_app()
    create_uc(app.state.conn, "uc@example.edu", "pw12345", role="instance_admin")
    return TestClient(app)


@pytest.fixture()
def auth(client):
    r = client.post("/api/v1/auth/login",
                    json={"email": "uc@example.edu", "password": "pw12345"})
    return {"Authorization": f"Bearer {r.json()['token']}"}
