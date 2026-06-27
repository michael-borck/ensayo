"""Self-registration, email verification, lockout, freeze, and build-cap tests."""

from __future__ import annotations

import pytest

from ensayo.api import service
from ensayo.api.ratelimit import limiter

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


@pytest.fixture(autouse=True)
def _reset_limiter():
    """The rate limiter is a process-global; clear it between tests."""
    limiter.reset_all()
    yield
    limiter.reset_all()


def _register(client, email="new1@example.edu", password="Password1", name="New"):
    return client.post("/api/v1/auth/register",
                       json={"email": email, "password": password, "display_name": name})


def _latest_code(conn, email):
    row = conn.execute(
        "SELECT code FROM uc_verifications v JOIN uc_accounts u ON u.id = v.uc_id "
        "WHERE u.email = ? AND v.used = 0 ORDER BY v.created_at DESC LIMIT 1",
        (email,)).fetchone()
    return row["code"] if row else None


# --- registration status (public) -----------------------------------------

def test_registration_status_default_open(client):
    r = client.get("/api/v1/auth/registration-status")
    assert r.status_code == 200
    body = r.json()
    assert body["registration_open"] is True
    assert body["email_configured"] is False  # no SMTP in tests


# --- register --------------------------------------------------------------

def test_register_creates_unverified_account(client):
    r = _register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "new1@example.edu"
    assert body["verification_sent"] is False  # no SMTP → code stored, not mailed
    # account exists, unverified
    uc = client.app.state.conn.execute(
        "SELECT is_verified FROM uc_accounts WHERE email = 'new1@example.edu'").fetchone()
    assert uc["is_verified"] == 0


def test_register_rejects_disallowed_domain(client, monkeypatch):
    monkeypatch.setenv("ALLOWED_DOMAINS", "curtin.edu.au")
    r = _register(client, email="someone@gmail.com")
    assert r.status_code == 403


def test_register_allows_whitelisted_domain(client, monkeypatch):
    monkeypatch.setenv("ALLOWED_DOMAINS", "curtin.edu.au")
    r = _register(client, email="someone@curtin.edu.au")
    assert r.status_code == 201, r.text


def test_register_duplicate_email_conflicts(client):
    assert _register(client).status_code == 201
    assert _register(client).status_code == 409


def test_register_short_password_rejected(client):
    r = _register(client, password="short")
    assert r.status_code == 422


# --- verify + login --------------------------------------------------------

def test_verify_email_issues_token_and_unlocks_login(client):
    _register(client)
    code = _latest_code(client.app.state.conn, "new1@example.edu")
    assert code
    # unverified login is refused
    bad = client.post("/api/v1/auth/login",
                      json={"email": "new1@example.edu", "password": "Password1"})
    assert bad.status_code == 403
    # verify
    r = client.post("/api/v1/auth/verify-email",
                    json={"email": "new1@example.edu", "code": code})
    assert r.status_code == 200, r.text
    assert r.json()["verified"] is True
    token = r.json()["token"]
    assert token
    # login now works
    ok = client.post("/api/v1/auth/login",
                     json={"email": "new1@example.edu", "password": "Password1"})
    assert ok.status_code == 200
    assert ok.json()["token"]


def test_verify_wrong_code_rejected(client):
    _register(client)
    r = client.post("/api/v1/auth/verify-email",
                    json={"email": "new1@example.edu", "code": "NOPE0000"})
    assert r.status_code == 400


def test_verify_code_single_use(client):
    _register(client)
    code = _latest_code(client.app.state.conn, "new1@example.edu")
    assert client.post("/api/v1/auth/verify-email",
                       json={"email": "new1@example.edu", "code": code}).status_code == 200
    # reusing the same code fails
    again = client.post("/api/v1/auth/verify-email",
                        json={"email": "new1@example.edu", "code": code})
    assert again.status_code == 400


def test_resend_invalidates_old_code(client):
    _register(client)
    old = _latest_code(client.app.state.conn, "new1@example.edu")
    assert client.post("/api/v1/auth/resend-verification",
                       json={"email": "new1@example.edu"}).status_code == 200
    new = _latest_code(client.app.state.conn, "new1@example.edu")
    assert new != old
    # old code no longer valid
    assert client.post("/api/v1/auth/verify-email",
                       json={"email": "new1@example.edu", "code": old}).status_code == 400
    # new code works
    assert client.post("/api/v1/auth/verify-email",
                       json={"email": "new1@example.edu", "code": new}).status_code == 200


# --- lockout ---------------------------------------------------------------

def test_account_lockout_after_repeated_failures(client):
    email, pw = "new1@example.edu", "Password1"
    _register(client)
    code = _latest_code(client.app.state.conn, email)
    client.post("/api/v1/auth/verify-email", json={"email": email, "code": code})
    # five wrong passwords are still 401…
    for _ in range(5):
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
        assert r.status_code == 401
    # …the sixth trips the lockout
    r = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 429


# --- freeze toggle ---------------------------------------------------------

def test_admin_can_freeze_registration(client, auth):
    r = client.put("/api/v1/admin/registration", headers=auth, json={"open": False})
    assert r.status_code == 200
    assert r.json()["registration_open"] is False
    # now sign-up is refused
    assert _register(client, email="frozen@example.edu").status_code == 403
    # reopen
    client.put("/api/v1/admin/registration", headers=auth, json={"open": True})
    assert _register(client, email="reopen@example.edu").status_code == 201


def test_non_admin_cannot_toggle_registration(client):
    _register(client)
    code = _latest_code(client.app.state.conn, "new1@example.edu")
    client.post("/api/v1/auth/verify-email", json={"email": "new1@example.edu", "code": code})
    tok = client.post("/api/v1/auth/login",
                      json={"email": "new1@example.edu", "password": "Password1"}).json()["token"]
    r = client.put("/api/v1/admin/registration",
                   headers={"Authorization": f"Bearer {tok}"}, json={"open": False})
    assert r.status_code == 403


def test_admin_sees_pending_codes_and_users(client, auth):
    _register(client, email="pending@example.edu", name="Pending Person")
    codes = client.get("/api/v1/admin/pending-codes", headers=auth).json()
    assert any(c["email"] == "pending@example.edu" for c in codes)
    assert all("code" in c for c in codes)  # code surfaced for admin relay
    users = client.get("/api/v1/admin/users", headers=auth).json()
    emails = [u["email"] for u in users]
    assert "pending@example.edu" in emails
    pending = next(u for u in users if u["email"] == "pending@example.edu")
    assert pending["is_verified"] is False
    assert pending["role"] == "uc"


# --- build concurrency cap -------------------------------------------------
# The cap logic (semaphore + build_deferred) is what matters here, not the
# Astro build itself, so ``generate`` is stubbed to a fast no-op that honours
# the ``build`` flag (creating dist/ only when it actually runs).
def _stub_generate(config_path, output_dir, *, base=None, with_llm=False,
                   build=True, log=None, **kw):
    from pathlib import Path
    if build:
        (Path(output_dir) / "dist").mkdir(parents=True, exist_ok=True)
    return None


def test_build_defers_when_concurrency_cap_reached(client, auth, monkeypatch):
    """With a cap of 1 and the single slot occupied, a build is deferred."""
    monkeypatch.setenv("MAX_CONCURRENT_BUILDS", "1")
    monkeypatch.setattr(service, "generate", _stub_generate)
    service._BUILD_SEM = None  # force re-init at the new size
    service._build_semaphore().acquire()  # occupy the only slot
    try:
        r = client.post("/api/v1/simulations", headers=auth,
                        json={"name": "Deferred Co", "company_yaml": SMALL_YAML, "build": True})
        assert r.status_code == 201, r.text
        assert r.json()["build_deferred"] is True
    finally:
        service._build_semaphore().release()
        service._BUILD_SEM = None  # let later tests re-init from their env


def test_build_runs_when_slot_free(client, auth, monkeypatch):
    monkeypatch.setattr(service, "generate", _stub_generate)
    r = client.post("/api/v1/simulations", headers=auth,
                    json={"name": "Built Co", "company_yaml": SMALL_YAML, "build": True})
    assert r.status_code == 201, r.text
    assert r.json()["build_deferred"] is False
