"""Phase 8 increment 6 tests: external-tool export endpoints."""

WF_YAML = """
company:
  name: "Flow Co"
employees:
  - name: "Ada Byron"
    role: "Hiring Manager"
    archetype: founder_ceo
"""

LONG = ("I have relevant experience building small applications, I work well in a "
        "team, I communicate clearly, and I am eager to learn quickly on the job "
        "and contribute from day one with a positive and reliable attitude.")


def _run_to_placement(client, auth):
    sim = client.post("/api/v1/simulations", headers=auth, json={
        "name": "Flow Sim", "company_yaml": WF_YAML,
        "auth_mode": "individual_account", "workflow": "internship", "build": False}).json()
    slug = sim["slug"]
    client.post(f"/api/v1/sims/{slug}/students/register",
                json={"email": "stu@uni.edu", "password": "pw123456"})
    tok = client.post(f"/api/v1/sims/{slug}/students/login",
                      json={"email": "stu@uni.edu", "password": "pw123456"}).json()["token"]
    sh = {"Authorization": f"Bearer {tok}"}
    app = client.post(f"/api/v1/sims/{slug}/applications", headers=sh, json={}).json()
    client.post(f"/api/v1/simulations/{sim['id']}/applications/{app['id']}/advance",
                headers=auth, json={"event": "application_submitted"})
    cid = client.post(f"/api/v1/sims/{slug}/conversations", headers=sh, json={
        "kind": "hiring_interview", "persona_slug": "ada-byron",
        "application_id": app["id"], "on_complete_event": "interview_result",
        "target_turns": 1}).json()["id"]
    client.post(f"/api/v1/sims/{slug}/conversations/{cid}/message", headers=sh,
                json={"text": LONG})
    client.post(f"/api/v1/sims/{slug}/conversations/{cid}/complete", headers=sh)
    return sim, slug, sh


def test_export_applications_and_conversations(client, auth):
    sim, slug, sh = _run_to_placement(client, auth)
    apps = client.get(f"/api/v1/simulations/{sim['id']}/export/applications", headers=auth).json()
    assert apps["schema_version"] == "1.0"
    assert len(apps["applications"]) == 1 and apps["applications"][0]["stage"] == "placement"

    convos = client.get(f"/api/v1/simulations/{sim['id']}/export/conversations", headers=auth).json()
    assert convos["conversations"][0]["assessment"]["outcome"] == "pass"
    assert convos["conversations"][0]["transcript"]  # full transcript exported


def test_export_cohort_and_journey(client, auth):
    sim, slug, sh = _run_to_placement(client, auth)
    cohort = client.get(f"/api/v1/simulations/{sim['id']}/export/cohort", headers=auth).json()
    assert cohort["students"] == 1
    assert cohort["applications_by_stage"].get("placement") == 1

    student_id = client.get(f"/api/v1/simulations/{sim['id']}/export/applications",
                            headers=auth).json()["applications"][0]["student_id"]
    journey = client.get(f"/api/v1/simulations/{sim['id']}/export/journey/{student_id}",
                         headers=auth).json()
    assert journey["schema_version"] == "1.0"
    assert len(journey["applications"]) == 1
    assert len(journey["conversations"]) == 1


def test_export_requires_auth(client):
    r = client.get("/api/v1/simulations/whatever/export/cohort")
    assert r.status_code == 401
