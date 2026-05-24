"""Phase 8 increment 2 tests: workflow engine wired into the runtime."""

WF_YAML = """
company:
  name: "Flow Co"
employees:
  - name: "Ada Byron"
    archetype: staff
"""


def _sim(client, auth, workflow="internship"):
    r = client.post("/api/v1/simulations", headers=auth, json={
        "name": "Flow Sim", "company_yaml": WF_YAML,
        "auth_mode": "individual_account", "workflow": workflow, "build": False})
    assert r.status_code == 201, r.text
    return r.json()


def _student_token(client, slug, email="stu@uni.edu"):
    client.post(f"/api/v1/sims/{slug}/students/register",
                json={"email": email, "password": "pw123456"})
    r = client.post(f"/api/v1/sims/{slug}/students/login",
                    json={"email": email, "password": "pw123456"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _bodies(client, slug, sh):
    return " ".join(m["body"] for m in
                    client.get(f"/api/v1/sims/{slug}/messages", headers=sh).json())


def test_application_lifecycle(client, auth):
    sim = _sim(client, auth)
    slug = sim["slug"]
    sh = _student_token(client, slug)

    # apply → initial stage + welcome message
    app = client.post(f"/api/v1/sims/{slug}/applications", headers=sh, json={}).json()
    assert app["current_stage"] == "application" and app["status"] == "active"
    assert "submit your application" in _bodies(client, slug, sh).lower()

    app_id = app["id"]
    # advance through the workflow (events come from "outside")
    adv = client.post(f"/api/v1/simulations/{sim['id']}/applications/{app_id}/advance",
                      headers=auth, json={"event": "application_submitted"}).json()
    assert adv["advanced"] is True and adv["stage"] == "interview"
    assert "booking" in adv["surfaces"]
    assert "book and attend" in _bodies(client, slug, sh).lower()

    # guarded transition: pass → placement, with assign_tasks action
    adv = client.post(f"/api/v1/simulations/{sim['id']}/applications/{app_id}/advance",
                      headers=auth,
                      json={"event": "interview_result", "context": {"outcome": "pass"}}).json()
    assert adv["stage"] == "placement"
    bodies = _bodies(client, slug, sh).lower()
    assert "you're placed" in bodies              # placement notify action
    assert "new tasks are available" in bodies    # assign_tasks action

    # finish
    client.post(f"/api/v1/simulations/{sim['id']}/applications/{app_id}/advance",
                headers=auth, json={"event": "tasks_complete"})
    fin = client.post(f"/api/v1/simulations/{sim['id']}/applications/{app_id}/advance",
                      headers=auth, json={"event": "exit_complete"}).json()
    assert fin["stage"] == "complete" and fin["terminal"] is True and fin["status"] == "completed"


def test_no_matching_transition_is_noop(client, auth):
    sim = _sim(client, auth)
    sh = _student_token(client, sim["slug"])
    app = client.post(f"/api/v1/sims/{sim['slug']}/applications", headers=sh, json={}).json()
    adv = client.post(
        f"/api/v1/simulations/{sim['id']}/applications/{app['id']}/advance",
        headers=auth, json={"event": "nonsense"}).json()
    assert adv["advanced"] is False and adv["stage"] == "application"


def test_reject_path_sets_rejected_status(client, auth):
    sim = _sim(client, auth)
    sh = _student_token(client, sim["slug"])
    app = client.post(f"/api/v1/sims/{sim['slug']}/applications", headers=sh, json={}).json()
    client.post(f"/api/v1/simulations/{sim['id']}/applications/{app['id']}/advance",
                headers=auth, json={"event": "application_submitted"})
    adv = client.post(f"/api/v1/simulations/{sim['id']}/applications/{app['id']}/advance",
                      headers=auth,
                      json={"event": "interview_result", "context": {"outcome": "fail"}}).json()
    assert adv["stage"] == "rejected" and adv["status"] == "rejected"


def test_duplicate_active_application_rejected(client, auth):
    sim = _sim(client, auth)
    sh = _student_token(client, sim["slug"])
    assert client.post(f"/api/v1/sims/{sim['slug']}/applications", headers=sh, json={}).status_code == 201
    assert client.post(f"/api/v1/sims/{sim['slug']}/applications", headers=sh, json={}).status_code == 409


def test_apply_without_workflow_fails(client, auth):
    sim = _sim(client, auth, workflow="")  # no workflow configured
    sh = _student_token(client, sim["slug"])
    r = client.post(f"/api/v1/sims/{sim['slug']}/applications", headers=sh, json={})
    assert r.status_code == 400


def test_uc_sees_applications(client, auth):
    sim = _sim(client, auth)
    sh = _student_token(client, sim["slug"])
    client.post(f"/api/v1/sims/{sim['slug']}/applications", headers=sh, json={})
    apps = client.get(f"/api/v1/simulations/{sim['id']}/applications", headers=auth).json()
    assert len(apps) == 1 and apps[0]["current_stage"] == "application"
