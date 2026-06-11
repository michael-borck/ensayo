"""Tests for the 2026-06 audit fixes: booking uniqueness, reset-code lockout,
token redaction, Gemini key handling, multi-site validate."""

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from ensayo.api.service import _redact_tokens
from ensayo.cli import main
from ensayo.llm import GeminiProvider

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

YAML = """
company:
  name: "Audit Co"
platform:
  booking_enabled: true
employees:
  - name: "Ada Byron"
    archetype: staff
"""


def _create(client, auth, **extra):
    r = client.post("/api/v1/simulations", headers=auth, json={
        "name": "Audit Sim", "company_yaml": YAML, "build": False, **extra})
    assert r.status_code == 201, r.text
    return r.json()


# --- booking double-booking guard (idx_booking_slot) ------------------------

def test_confirmed_slot_unique_at_db_level(client, auth):
    sim = _create(client, auth)
    slug = sim["slug"]
    r1 = client.post(f"/api/v1/sims/{slug}/bookings",
                     json={"employee_slug": "ada-byron",
                           "slot_start": "2026-06-15T09:00:00"})
    assert r1.status_code == 201, r1.text
    # The API pre-check catches a same-slot retry…
    r2 = client.post(f"/api/v1/sims/{slug}/bookings",
                     json={"employee_slug": "ada-byron",
                           "slot_start": "2026-06-15T09:00:00"})
    assert r2.status_code == 400
    # …and the DB constraint catches the check-then-insert race itself.
    conn = client.app.state.conn
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO bookings (id, simulation_id, employee_slug, slot_start, "
            "slot_end, status, created_at) VALUES ('x', ?, 'ada-byron', "
            "'2026-06-15T09:00:00', '2026-06-15T09:30:00', 'confirmed', 'now')",
            (sim["id"],))
    # A cancelled slot can be rebooked (the index is partial).
    bid = r1.json()["id"]
    assert client.post(f"/api/v1/simulations/{sim['id']}/bookings/{bid}/cancel",
                       headers=auth).status_code == 200
    r3 = client.post(f"/api/v1/sims/{slug}/bookings",
                     json={"employee_slug": "ada-byron",
                           "slot_start": "2026-06-15T09:00:00"})
    assert r3.status_code == 201, r3.text


# --- reset codes: 8 digits + lockout after repeated wrong guesses -----------

def test_reset_code_lockout(client, auth):
    sim = _create(client, auth, auth_mode="individual_account")
    slug = sim["slug"]
    client.post(f"/api/v1/sims/{slug}/students/register",
                json={"email": "s@uni.edu", "name": "Sam", "password": "pw123456"})
    req = client.post(f"/api/v1/sims/{slug}/students/request-reset",
                      json={"email": "s@uni.edu"})
    code = req.json()["code"]  # SMTP unconfigured → surfaced for the UC
    assert len(code) == 8 and code.isdigit()
    for _ in range(5):
        bad = client.post(f"/api/v1/sims/{slug}/students/reset",
                          json={"email": "s@uni.edu", "code": "00000000",
                                "new_password": "newpw1234"})
        assert bad.status_code == 400
    # Five wrong guesses burned the code — even the right one no longer works.
    burned = client.post(f"/api/v1/sims/{slug}/students/reset",
                         json={"email": "s@uni.edu", "code": code,
                               "new_password": "newpw1234"})
    assert burned.status_code == 400


def test_reset_code_still_works_within_attempts(client, auth):
    sim = _create(client, auth, auth_mode="individual_account")
    slug = sim["slug"]
    client.post(f"/api/v1/sims/{slug}/students/register",
                json={"email": "s@uni.edu", "name": "Sam", "password": "pw123456"})
    code = client.post(f"/api/v1/sims/{slug}/students/request-reset",
                       json={"email": "s@uni.edu"}).json()["code"]
    client.post(f"/api/v1/sims/{slug}/students/reset",
                json={"email": "s@uni.edu", "code": "00000000",
                      "new_password": "newpw1234"})
    ok = client.post(f"/api/v1/sims/{slug}/students/reset",
                     json={"email": "s@uni.edu", "code": code,
                           "new_password": "newpw1234"})
    assert ok.status_code == 200
    login = client.post(f"/api/v1/sims/{slug}/students/login",
                        json={"email": "s@uni.edu", "password": "newpw1234"})
    assert login.status_code == 200


# --- secrets hygiene ---------------------------------------------------------

def test_git_errors_redact_access_tokens():
    msg = _redact_tokens(
        "git push -f https://x-access-token:ghp_secret123@github.com/o/r failed")
    assert "ghp_secret123" not in msg
    assert "x-access-token:***@github.com" in msg


def test_gemini_key_sent_as_header_not_query(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers", {})

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"candidates": [{"content": {"parts": [{"text": "hi"}]}}],
                        "usageMetadata": {}}
        return R()

    monkeypatch.setattr("ensayo.llm.httpx.post", fake_post)
    GeminiProvider("gemini-2.0-flash", "sekret").generate("hello")
    assert "sekret" not in captured["url"]
    assert captured["headers"].get("x-goog-api-key") == "sekret"


# --- CLI: validate auto-detects multi-site configs ---------------------------

def test_validate_multisite_config():
    res = CliRunner().invoke(
        main, ["validate", "-c", str(EXAMPLES / "workready-mini" / "simulation.yaml")])
    assert res.exit_code == 0, res.output
    assert "multi-site" in res.output
    assert "Companies:" in res.output
