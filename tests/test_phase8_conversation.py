"""Phase 8 increment 3 tests: 1-on-1 conversation surface + assessment loop."""

from ensayo.assess import assess
from ensayo.llm import ProviderSpec, StubProvider

WF_YAML = """
company:
  name: "Flow Co"
employees:
  - name: "Ada Byron"
    role: "Hiring Manager"
    archetype: founder_ceo
"""

LONG_ANSWER = (
    "I have spent the last two years building small web applications and I am "
    "comfortable picking up new tools quickly. In my last project I led the data "
    "migration, coordinated with two teammates, and we shipped on time despite a "
    "tricky deadline. I learn fast and I ask questions early when I am unsure."
)


def _sim(client, auth):
    r = client.post("/api/v1/simulations", headers=auth, json={
        "name": "Flow Sim", "company_yaml": WF_YAML,
        "auth_mode": "individual_account", "workflow": "internship", "build": False})
    assert r.status_code == 201, r.text
    return r.json()


def _student(client, slug, email="stu@uni.edu"):
    client.post(f"/api/v1/sims/{slug}/students/register",
                json={"email": email, "password": "pw123456"})
    r = client.post(f"/api/v1/sims/{slug}/students/login",
                    json={"email": email, "password": "pw123456"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


# --- assessment helper -----------------------------------------------------

def test_assess_stub_is_deterministic_and_banded():
    p, spec = StubProvider(), ProviderSpec(provider="stub")
    short = assess(p, spec, content="ok", kind="hiring_interview")
    rich = assess(p, spec, content=LONG_ANSWER * 2, kind="hiring_interview")
    assert 0 <= short.score <= 100 and rich.score >= short.score
    assert rich.outcome == "pass"


# --- conversation surface --------------------------------------------------

def test_conversation_basic_flow(client, auth):
    sim = _sim(client, auth)
    slug = sim["slug"]
    sh = _student(client, slug)
    start = client.post(f"/api/v1/sims/{slug}/conversations", headers=sh,
                        json={"kind": "coaching", "persona_slug": "ada-byron",
                              "target_turns": 2}).json()
    assert start["status"] == "active"
    assert start["transcript"][0]["role"] == "assistant"  # persona opens

    sid = start["id"]
    r1 = client.post(f"/api/v1/sims/{slug}/conversations/{sid}/message", headers=sh,
                     json={"text": "Here is my reflection on the week."}).json()
    assert r1["turn_count"] == 1 and r1["ready_to_complete"] is False
    r2 = client.post(f"/api/v1/sims/{slug}/conversations/{sid}/message", headers=sh,
                     json={"text": LONG_ANSWER}).json()
    assert r2["ready_to_complete"] is True

    done = client.post(f"/api/v1/sims/{slug}/conversations/{sid}/complete", headers=sh).json()
    assert "score" in done["assessment"] and done["advanced"] is None  # not wired to an app


def test_interview_completes_and_advances_application(client, auth):
    """The loop: interview conversation → assessment → event → workflow advances."""
    sim = _sim(client, auth)
    slug = sim["slug"]
    sh = _student(client, slug)

    app = client.post(f"/api/v1/sims/{slug}/applications", headers=sh, json={}).json()
    # move to the interview stage
    client.post(f"/api/v1/simulations/{sim['id']}/applications/{app['id']}/advance",
                headers=auth, json={"event": "application_submitted"})

    start = client.post(f"/api/v1/sims/{slug}/conversations", headers=sh, json={
        "kind": "hiring_interview", "persona_slug": "ada-byron",
        "application_id": app["id"], "on_complete_event": "interview_result",
        "target_turns": 1}).json()
    sid = start["id"]
    client.post(f"/api/v1/sims/{slug}/conversations/{sid}/message", headers=sh,
                json={"text": LONG_ANSWER})

    done = client.post(f"/api/v1/sims/{slug}/conversations/{sid}/complete", headers=sh).json()
    assert done["assessment"]["outcome"] == "pass"
    assert done["advanced"]["advanced"] is True
    assert done["advanced"]["stage"] == "placement"

    # the application really moved
    apps = client.get(f"/api/v1/simulations/{sim['id']}/applications", headers=auth).json()
    assert apps[0]["current_stage"] == "placement"


def test_cannot_message_after_complete(client, auth):
    sim = _sim(client, auth)
    slug = sim["slug"]
    sh = _student(client, slug)
    sid = client.post(f"/api/v1/sims/{slug}/conversations", headers=sh,
                      json={"kind": "coaching", "persona_slug": "ada-byron",
                            "target_turns": 1}).json()["id"]
    client.post(f"/api/v1/sims/{slug}/conversations/{sid}/complete", headers=sh)
    r = client.post(f"/api/v1/sims/{slug}/conversations/{sid}/message", headers=sh,
                    json={"text": "hello?"})
    assert r.status_code == 400
