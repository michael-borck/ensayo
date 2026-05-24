"""Phase 5 tests: individual student accounts, whitelist, reset, management."""

YAML = """
company:
  name: "Class Co"
employees:
  - name: "Ada Byron"
    archetype: staff
"""


def _create(client, auth, auth_mode="individual_account", audience="adults", name="Class Sim"):
    yaml = YAML if audience == "adults" else YAML.replace(
        'name: "Class Co"', 'name: "Class Co"\n  ').replace(
        "company:", "company:") + "audience: minors\n"
    r = client.post("/api/v1/simulations", headers=auth, json={
        "name": name, "company_yaml": yaml, "auth_mode": auth_mode, "build": False})
    assert r.status_code == 201, r.text
    return r.json()


def test_individual_register_and_login(client, auth):
    sim = _create(client, auth)
    slug = sim["slug"]
    reg = client.post(f"/api/v1/sims/{slug}/students/register",
                      json={"email": "sam@uni.edu", "name": "Sam", "password": "pw123456"})
    assert reg.status_code == 201, reg.text

    ok = client.post(f"/api/v1/sims/{slug}/students/login",
                     json={"email": "sam@uni.edu", "password": "pw123456"})
    assert ok.status_code == 200 and ok.json()["token"]

    bad = client.post(f"/api/v1/sims/{slug}/students/login",
                      json={"email": "sam@uni.edu", "password": "wrong"})
    assert bad.status_code == 401

    dup = client.post(f"/api/v1/sims/{slug}/students/register",
                      json={"email": "sam@uni.edu", "name": "Sam", "password": "pw123456"})
    assert dup.status_code == 409


def test_whitelist_enforced(client, auth):
    sim = _create(client, auth)
    slug = sim["slug"]
    client.post(f"/api/v1/simulations/{sim['id']}/whitelist", headers=auth,
                json={"emails": ["allowed@uni.edu"]})
    blocked = client.post(f"/api/v1/sims/{slug}/students/register",
                          json={"email": "other@uni.edu", "password": "pw123456"})
    assert blocked.status_code == 403
    ok = client.post(f"/api/v1/sims/{slug}/students/register",
                     json={"email": "allowed@uni.edu", "password": "pw123456"})
    assert ok.status_code == 201


def test_whitelist_csv_upload(client, auth):
    sim = _create(client, auth)
    r = client.post(f"/api/v1/simulations/{sim['id']}/whitelist", headers=auth,
                    json={"csv": "name,email\nAda,a@uni.edu\nBeth,b@uni.edu\n"})
    assert r.status_code == 200 and r.json()["added"] == 2
    wl = client.get(f"/api/v1/simulations/{sim['id']}/whitelist", headers=auth).json()
    assert set(wl["emails"]) == {"a@uni.edu", "b@uni.edu"}


def test_email_only_autocreates(client, auth):
    sim = _create(client, auth, auth_mode="email_only")
    r = client.post(f"/api/v1/sims/{sim['slug']}/students/login",
                    json={"email": "ezra@uni.edu"})
    assert r.status_code == 200 and r.json()["token"]
    students = client.get(f"/api/v1/simulations/{sim['id']}/students", headers=auth).json()
    assert len(students) == 1 and students[0]["email"] == "ezra@uni.edu"


def test_password_reset_without_smtp(client, auth, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    sim = _create(client, auth)
    slug = sim["slug"]
    client.post(f"/api/v1/sims/{slug}/students/register",
                json={"email": "rae@uni.edu", "password": "oldpass1"})
    req = client.post(f"/api/v1/sims/{slug}/students/request-reset",
                      json={"email": "rae@uni.edu"}).json()
    assert req["sent"] is False and "code" in req  # surfaced for manual relay
    rs = client.post(f"/api/v1/sims/{slug}/students/reset",
                     json={"email": "rae@uni.edu", "code": req["code"], "new_password": "newpass1"})
    assert rs.status_code == 200
    ok = client.post(f"/api/v1/sims/{slug}/students/login",
                     json={"email": "rae@uni.edu", "password": "newpass1"})
    assert ok.status_code == 200


def test_uc_management_reset_delete_export(client, auth):
    sim = _create(client, auth)
    slug = sim["slug"]
    client.post(f"/api/v1/sims/{slug}/students/register",
                json={"email": "kim@uni.edu", "name": "Kim", "password": "pw123456"})
    sid = client.get(f"/api/v1/simulations/{sim['id']}/students", headers=auth).json()[0]["id"]

    m = client.get(f"/api/v1/simulations/{sim['id']}/students/metrics", headers=auth).json()
    assert m["total"] == 1 and m["active"] == 1

    # UC resets password
    client.post(f"/api/v1/simulations/{sim['id']}/students/{sid}/reset-password",
                headers=auth, json={"new_password": "ucset123"})
    assert client.post(f"/api/v1/sims/{slug}/students/login",
                       json={"email": "kim@uni.edu", "password": "ucset123"}).status_code == 200

    # soft delete redacts PII
    d = client.delete(f"/api/v1/simulations/{sim['id']}/students/{sid}", headers=auth)
    assert d.status_code == 200
    after = client.get(f"/api/v1/simulations/{sim['id']}/students", headers=auth).json()[0]
    assert after["status"] == "deleted" and after["email"] is None

    exp = client.get(f"/api/v1/simulations/{sim['id']}/students/export", headers=auth)
    assert exp.status_code == 200 and exp.text.startswith("id,email,name,status")


def test_minors_forces_shared_password(client, auth):
    sim = _create(client, auth, auth_mode="individual_account", audience="minors")
    assert sim["auth_mode"] == "shared_password"
