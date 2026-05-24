"""Phase 3 completion tests: Save/Publish, GitHub publish, booking, visibility."""

import subprocess
from datetime import date, timedelta
from pathlib import Path

YAML_BASE = """
company:
  name: "Test Co"
employees:
  - name: "Ada Byron"
    role: "Managing Director"
    archetype: founder_ceo
"""

YAML_BOOKING = """
company:
  name: "Booking Co"
platform:
  booking_enabled: true
employees:
  - name: "Ada Byron"
    role: "Managing Director"
    archetype: founder_ceo
"""


def _create(client, auth, yaml=YAML_BASE, name="Sim", **extra):
    body = {"name": name, "company_yaml": yaml, "build": False, **extra}
    r = client.post("/api/v1/simulations", headers=auth, json=body)
    assert r.status_code == 201, r.text
    return r.json()


# --- Save vs Publish edit model -------------------------------------------

def test_update_marks_unpublished(client, auth):
    sim = _create(client, auth)
    assert sim["has_unpublished_changes"] is False
    new_yaml = YAML_BASE.replace("Test Co", "Renamed Co")
    r = client.put(f"/api/v1/simulations/{sim['id']}", headers=auth,
                   json={"company_yaml": new_yaml, "build": False})
    assert r.status_code == 200, r.text
    assert r.json()["has_unpublished_changes"] is True
    # config cache reflects the edit
    got = client.get(f"/api/v1/simulations/{sim['id']}", headers=auth).json()
    assert got["config_cache"]["company"]["name"] == "Renamed Co"


def test_get_yaml_roundtrips(client, auth):
    sim = _create(client, auth)
    r = client.get(f"/api/v1/simulations/{sim['id']}/yaml", headers=auth)
    assert r.status_code == 200
    assert "Test Co" in r.json()["company_yaml"]


# --- publish to GitHub Pages (local bare remote stands in for GitHub) ------

def test_publish_pushes_main_and_gh_pages(client, auth, tmp_path):
    sim = _create(client, auth)
    clone = Path(sim["working_clone_path"])
    # Simulate a built site (build=False above, so make a dist/).
    (clone / "dist").mkdir(exist_ok=True)
    (clone / "dist" / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")

    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)

    r = client.post(f"/api/v1/simulations/{sim['id']}/repo", headers=auth,
                    json={"repo_url": str(bare)})
    assert r.status_code == 200, r.text

    r = client.post(f"/api/v1/simulations/{sim['id']}/publish", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["published"] is True

    refs = subprocess.run(["git", "ls-remote", str(bare)], capture_output=True,
                          text=True, check=True).stdout
    assert "refs/heads/main" in refs
    assert "refs/heads/gh-pages" in refs

    # gh-pages contains the built site + .nojekyll
    out = tmp_path / "checkout"
    subprocess.run(["git", "clone", "-q", "-b", "gh-pages", str(bare), str(out)], check=True)
    assert (out / "index.html").exists()
    assert (out / ".nojekyll").exists()

    # publishing clears the unpublished flag
    got = client.get(f"/api/v1/simulations/{sim['id']}", headers=auth).json()
    assert got["has_unpublished_changes"] is False
    assert got["status"] == "active"


def test_publish_without_repo_is_noop(client, auth):
    sim = _create(client, auth)
    r = client.post(f"/api/v1/simulations/{sim['id']}/publish", headers=auth)
    assert r.status_code == 200
    assert r.json()["published"] is False


# --- booking ---------------------------------------------------------------

def _a_weekday() -> str:
    d = date(2026, 6, 1)
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d.isoformat()


def test_booking_flow(client, auth):
    sim = _create(client, auth, yaml=YAML_BOOKING, name="Booking Sim")
    slug = sim["slug"]
    day = _a_weekday()

    slots = client.get(f"/api/v1/sims/{slug}/availability",
                       params={"employee": "ada-byron", "date": day}).json()["slots"]
    assert len(slots) > 0
    first = slots[0]["slot_start"]

    r = client.post(f"/api/v1/sims/{slug}/bookings",
                    json={"employee_slug": "ada-byron", "slot_start": first,
                          "student_name": "Sam"})
    assert r.status_code == 201, r.text

    # double-booking the same slot is rejected
    r2 = client.post(f"/api/v1/sims/{slug}/bookings",
                     json={"employee_slug": "ada-byron", "slot_start": first})
    assert r2.status_code == 400

    # the slot is no longer offered
    slots2 = client.get(f"/api/v1/sims/{slug}/availability",
                        params={"employee": "ada-byron", "date": day}).json()["slots"]
    assert all(s["slot_start"] != first for s in slots2)

    # UC sees the booking
    ucb = client.get(f"/api/v1/simulations/{sim['id']}/bookings", headers=auth).json()
    assert len(ucb) == 1 and ucb[0]["student_name"] == "Sam"


def test_booking_disabled_rejected(client, auth):
    sim = _create(client, auth)  # no booking_enabled
    r = client.post(f"/api/v1/sims/{sim['slug']}/bookings",
                    json={"employee_slug": "ada-byron", "slot_start": "2026-06-01T09:00:00"})
    assert r.status_code == 400


# --- visibility rules ------------------------------------------------------

def test_visibility_hide_and_delete(client, auth):
    sim = _create(client, auth)
    slug = sim["slug"]
    r = client.post(f"/api/v1/simulations/{sim['id']}/visibility", headers=auth,
                    json={"target_type": "document", "target_id": "secret-memo",
                          "action": "hide"})
    assert r.status_code == 201, r.text
    rule_id = r.json()["id"]

    hidden = client.get(f"/api/v1/sims/{slug}/visibility").json()["hidden"]
    assert {"target_type": "document", "target_id": "secret-memo"} in hidden

    d = client.delete(f"/api/v1/simulations/{sim['id']}/visibility/{rule_id}", headers=auth)
    assert d.status_code == 200
    hidden2 = client.get(f"/api/v1/sims/{slug}/visibility").json()["hidden"]
    assert hidden2 == []


def test_visibility_future_datetime_not_yet_active(client, auth):
    sim = _create(client, auth)
    client.post(f"/api/v1/simulations/{sim['id']}/visibility", headers=auth,
                json={"target_type": "page", "target_id": "results",
                      "action": "hide", "trigger_type": "datetime",
                      "trigger_value": "2099-01-01T00:00:00+00:00"})
    # a future "hide" rule isn't active yet → nothing hidden
    hidden = client.get(f"/api/v1/sims/{sim['slug']}/visibility").json()["hidden"]
    assert hidden == []
