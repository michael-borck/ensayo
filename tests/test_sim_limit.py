"""Per-account simulation limit (MAX_SIMS_PER_UC) + usage endpoint."""

from __future__ import annotations


def _co(name: str) -> str:
    return (f'company:\n  name: "{name}"\n'
            'employees:\n  - name: "Ada"\n    role: "Director"\n    archetype: founder_ceo\n')


def _create(client, auth, name, co):
    return client.post("/api/v1/simulations", headers=auth,
                       json={"name": name, "company_yaml": _co(co), "build": False})


def test_limit_blocks_fourth_and_reports_usage(client, auth, monkeypatch):
    monkeypatch.setenv("MAX_SIMS_PER_UC", "3")
    for i in range(3):
        r = _create(client, auth, f"S{i}", f"Co{i}")
        assert r.status_code == 201, r.text
    # usage endpoint reflects the cap
    usage = client.get("/api/v1/usage", headers=auth).json()
    assert usage["count"] == 3 and usage["limit"] == 3
    # the fourth is refused with a clear message
    r = _create(client, auth, "S3", "Co3")
    assert r.status_code == 400
    assert "limit" in r.json()["detail"].lower()


def test_limit_is_configurable(client, auth, monkeypatch):
    monkeypatch.setenv("MAX_SIMS_PER_UC", "1")
    assert _create(client, auth, "A", "Ca").status_code == 201
    assert _create(client, auth, "B", "Cb").status_code == 400
    d = client.get("/api/v1/usage", headers=auth).json()
    assert d["count"] == 1 and d["limit"] == 1


def test_usage_requires_auth(client):
    assert client.get("/api/v1/usage").status_code == 401
