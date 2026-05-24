"""Phase 8 increment 3b tests: document submission + group chat surfaces."""

WF_YAML = """
company:
  name: "Flow Co"
employees:
  - name: "Ada Byron"
    archetype: staff
"""

LONG = ("Here is my completed task writeup. I documented the onboarding process "
        "step by step, noted who owns each step, recorded how long each takes, and "
        "flagged the common mistakes new hires make so the guide is genuinely usable "
        "without supervision. I also added a short checklist at the end.")


def _sim(client, auth):
    r = client.post("/api/v1/simulations", headers=auth, json={
        "name": "Flow Sim", "company_yaml": WF_YAML,
        "auth_mode": "individual_account", "workflow": "internship", "build": False})
    assert r.status_code == 201, r.text
    return r.json()


def _student(client, slug):
    client.post(f"/api/v1/sims/{slug}/students/register",
                json={"email": "stu@uni.edu", "password": "pw123456"})
    r = client.post(f"/api/v1/sims/{slug}/students/login",
                    json={"email": "stu@uni.edu", "password": "pw123456"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


# --- document submission ---------------------------------------------------

def test_submission_reviewed_immediately(client, auth):
    sim = _sim(client, auth)
    slug = sim["slug"]
    sh = _student(client, slug)
    r = client.post(f"/api/v1/sims/{slug}/submissions", headers=sh,
                    json={"title": "Task 1", "body": LONG}).json()
    assert r["review_available"] is True
    assert r["outcome"] in ("pass", "fail")
    assert "score" in r


def test_submission_review_is_lazy_gated(client, auth):
    sim = _sim(client, auth)
    slug = sim["slug"]
    sh = _student(client, slug)
    r = client.post(f"/api/v1/sims/{slug}/submissions", headers=sh,
                    json={"title": "Task 1", "body": LONG,
                          "review_delay_seconds": 3600}).json()
    assert r["review_available"] is False
    assert r["status"] == "under_review"
    assert r["outcome"] is None  # feedback hidden until deliver_at


def test_passing_submission_advances_application(client, auth):
    sim = _sim(client, auth)
    slug = sim["slug"]
    sh = _student(client, slug)
    app = client.post(f"/api/v1/sims/{slug}/applications", headers=sh, json={}).json()
    # drive to the placement stage (where tasks live)
    for ev in [{"event": "application_submitted"},
               {"event": "interview_result", "context": {"outcome": "pass"}}]:
        client.post(f"/api/v1/simulations/{sim['id']}/applications/{app['id']}/advance",
                    headers=auth, json=ev)

    r = client.post(f"/api/v1/sims/{slug}/submissions", headers=sh, json={
        "title": "Placement Task", "body": LONG, "application_id": app["id"],
        "on_complete_event": "tasks_complete"}).json()
    assert r["outcome"] == "pass"
    assert r["advanced"]["advanced"] is True
    assert r["advanced"]["stage"] == "exit_interview"


# --- group chat ------------------------------------------------------------

def test_group_chat_beats_and_participation(client, auth):
    sim = _sim(client, auth)
    slug = sim["slug"]
    sh = _student(client, slug)
    start = client.post(f"/api/v1/sims/{slug}/group-chats", headers=sh, json={
        "occasion": "Team lunch", "participants": ["Ada", "Marcus"],
        "beats": ["Welcome to the team!", "How's your first week going?"],
        "beat_interval_seconds": 0}).json()
    authors = {p["author_name"] for p in start["posts"]}
    assert "Ada" in authors
    assert any(p["content"] == "— Team lunch —" for p in start["posts"])  # system intro

    gid = start["id"]
    client.post(f"/api/v1/sims/{slug}/group-chats/{gid}/post", headers=sh,
                json={"text": "Going well, thanks!"})
    client.post(f"/api/v1/sims/{slug}/group-chats/{gid}/post", headers=sh,
                json={"text": "Excited to get started."})
    feed = client.get(f"/api/v1/sims/{slug}/group-chats/{gid}", headers=sh).json()
    assert any(p["author_kind"] == "student" for p in feed["posts"])

    done = client.post(f"/api/v1/sims/{slug}/group-chats/{gid}/complete", headers=sh).json()
    assert done["student_posts"] == 2 and "Good engagement" in done["participation_notes"]


def test_group_chat_beats_are_lazy(client, auth):
    sim = _sim(client, auth)
    slug = sim["slug"]
    sh = _student(client, slug)
    start = client.post(f"/api/v1/sims/{slug}/group-chats", headers=sh, json={
        "occasion": "Standup", "participants": ["Ada"],
        "beats": ["First beat", "Second beat"],
        "beat_interval_seconds": 3600}).json()
    # only the immediate system post is delivered; future beats are gated
    kinds = [p["author_kind"] for p in start["posts"]]
    assert kinds == ["system"]
