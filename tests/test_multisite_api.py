"""Multi-site simulation lifecycle via the dashboard API (create/config/update)."""

from __future__ import annotations

import pytest

from ensayo.api import service


def _sim() -> dict:
    return {"name": "Mini Portal", "portal": {"title": "Mini", "description": "d"},
            "companies": [
                {"company": {"name": "Acme", "scenario": {"type": "growth", "name": "x"}},
                 "theme": "tech-modern",
                 "employees": [{"name": "Ada", "role": "CEO", "archetype": "founder_ceo"}]},
                {"company": {"name": "Beta Co", "scenario": {"type": "growth", "name": "y"}},
                 "theme": "finance-traditional",
                 "employees": [{"name": "Bob", "role": "CFO", "archetype": "finance_manager"}]},
            ]}


def test_create_multisite_via_dashboard(client, auth, monkeypatch):
    monkeypatch.setattr(service, "generate_multisite", lambda *a, **k: None)  # no Astro build
    r = client.post("/api/v1/simulations", headers=auth,
                    json={"name": "Mini Portal", "simulation": _sim(), "build": False})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["slug"] == "mini-portal"
    assert body["type"] == "multi_site"
    assert body["audience"] == "adults"  # multi-site is adults-only


def test_get_config_returns_simulation_config(client, auth, monkeypatch):
    monkeypatch.setattr(service, "generate_multisite", lambda *a, **k: None)
    sim = client.post("/api/v1/simulations", headers=auth,
                      json={"name": "Mini Portal", "simulation": _sim(), "build": False}).json()
    cfg = client.get(f"/api/v1/simulations/{sim['id']}/config", headers=auth).json()
    assert cfg["type"] == "multi_site"
    assert [c["company"]["name"] for c in cfg["companies"]] == ["Acme", "Beta Co"]
    assert cfg["portal"]["title"] == "Mini"


def test_update_multisite_round_trips(client, auth, monkeypatch):
    monkeypatch.setattr(service, "generate_multisite", lambda *a, **k: None)
    sim = client.post("/api/v1/simulations", headers=auth,
                      json={"name": "Mini Portal", "simulation": _sim(), "build": False}).json()
    new = _sim()
    new["portal"]["title"] = "Mini Updated"
    r = client.put(f"/api/v1/simulations/{sim['id']}", headers=auth,
                   json={"simulation": new, "build": False})
    assert r.status_code == 200, r.text
    cfg = client.get(f"/api/v1/simulations/{sim['id']}/config", headers=auth).json()
    assert cfg["portal"]["title"] == "Mini Updated"


def test_multisite_rejects_minors(client, auth):
    sim = _sim()
    sim["audience"] = "minors"
    r = client.post("/api/v1/simulations", headers=auth,
                    json={"name": "Bad", "simulation": sim, "build": False})
    assert r.status_code == 422  # spec §7.5: multi-site unavailable for minors


def test_multisite_needs_a_company(client, auth):
    r = client.post("/api/v1/simulations", headers=auth,
                    json={"name": "Empty", "simulation": {"name": "Empty", "companies": []}, "build": False})
    assert r.status_code == 422



def test_multisite_known_documents_round_trips(client, auth, monkeypatch):
    """known_documents (doc↔persona mapping) survives multi-site create→config."""
    monkeypatch.setattr(service, "generate_multisite", lambda *a, **k: None)
    sim_obj = _sim()
    sim_obj["companies"][0]["documents"] = [
        {"title": "Security Policy", "type": "policy", "content": "Use 2FA."},
        {"title": "Employee Handbook", "type": "internal", "content": "Be good."},
    ]
    sim_obj["companies"][0]["employees"][0]["customisation"] = {
        "known_documents": ["Security Policy"],
        "background": "Ada knows security.",
    }
    sim = client.post("/api/v1/simulations", headers=auth,
                      json={"name": "Doc Map Portal", "simulation": sim_obj, "build": False}).json()
    cfg = client.get(f"/api/v1/simulations/{sim['id']}/config", headers=auth).json()
    acme = cfg["companies"][0]
    emp = acme["employees"][0]
    assert emp["customisation"]["known_documents"] == ["Security Policy"]
    assert emp["customisation"]["background"] == "Ada knows security."
    assert [d["title"] for d in acme["documents"]] == ["Security Policy", "Employee Handbook"]


def test_multisite_templates_endpoint(client, auth):
    """Template gallery endpoint returns bundled shapes with companies."""
    r = client.get("/api/v1/multisite-templates", headers=auth)
    assert r.status_code == 200, r.text
    templates = r.json()
    ids = {t["id"] for t in templates}
    assert "internship" in ids
    assert "medical_network" in ids
    assert "legal_practice" in ids
    # Each template has portal + companies + workflow
    for t in templates:
        assert t["label"]
        assert t["workflow"]
        assert t["portal"]["title"]
        assert len(t["companies"]) >= 1
        for c in t["companies"]:
            assert c["name"]
            assert c["theme"]