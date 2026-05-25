# Acceptance Testing (manual UAT)

A scripted walkthrough of Ensayo's features as **user stories** — run these by hand
against a live instance to confirm everything works end to end. Each scenario has
**Steps** and an **Expected** result; tick the box when it passes.

The automated suite (`pytest`, 105 tests) covers the API and generator; this
document covers the *human* journeys and the UI.

---

## 0. Setup

```bash
# from the repo
uv run ensayo admin create-uc --email teacher@uni.edu --admin   # make an instance admin
uv run ensayo serve                                             # http://127.0.0.1:8000
```

- Dashboard: <http://127.0.0.1:8000/admin/>
- Student portal: <http://127.0.0.1:8000/portal/>
- Generated sites (local): `http://127.0.0.1:8000/sims/<slug>/`

> **Know before you test**
> - **No LLM/AnythingLLM needed** — everything works in stub/dry-run mode.
> - **Multi-site sims** are created with the CLI (`ensayo generate`), not the
>   dashboard. The dashboard create flow is single-company.
> - **Workflow-driven student journeys** (applications/interviews/etc.) need a sim
>   created with a `workflow` set. The wizard doesn't expose `workflow` yet, so
>   scenario F1 uses the API to create one. *(Known gap — see "Gaps" at the end.)*

---

## A. Authoring (UC)

### A1 — Create a simulation with the guided wizard ☐
**Steps:** /admin/ → sign in → **+ New simulation** → fill Basics (name, audience
*adults*, auth *shared password*, theme *tech-modern*) → Company → Scenario → add 2
People → add 1 Document → Finish → tick *Build the site* → **Create**.
**Expected:** sim appears in the list; **View ↗** opens a built site with a home
page, staff directory, those people (each with a keyword chatbot), and the document.

### A2 — Create from raw YAML (advanced) ☐
**Steps:** **+ New simulation** → **Advanced: paste YAML** → paste
`examples/nexuspoint/company.yaml` → Create.
**Expected:** 7 employees + 5 documents generated; site builds.

### A3 — Edit (Save) then Publish ☐
**Steps:** **Edit** a sim → change the tagline → **Save changes**. Then on the card,
note the *unpublished changes* badge. (Publishing needs a GitHub repo + token; if
unconfigured, **Publish** reports "no repo connected".)
**Expected:** Save regenerates the site (re-open View ↗ to see the change) and the
card shows *unpublished changes*.

### A4 — LLM-assisted generation (stub) ☐
**Steps:** Create from `examples/sparse/company.yaml` (4 employees, names only) with
*Generate content with LLM* ticked.
**Expected:** each employee page has a backstory; the scenario and documents have
draft bodies (marked "stub"). (With a real provider set, content is real.)

### A5 — Theme gallery ☐
**Steps:** `uv run ensayo gallery -o ./gallery` → `python3 -m http.server -d ./gallery 8001`.
**Expected:** an index links to the demo rendered in each company theme; each looks
visually distinct (tech-modern dark, finance serif, mining industrial, etc.).

---

## B. Student authentication modes

### B1 — Shared password ☐
**Steps:** create a sim with auth *shared password* + a password.
`POST /api/v1/auth/student/verify {slug, password}`.
**Expected:** correct password → `{ok:true}`; wrong → `{ok:false}`.

### B2 — Individual accounts ☐
**Steps:** sim with auth *individual accounts*. Portal → sign in → **Register**
(email + password) → then sign in.
**Expected:** registration succeeds; login returns a session; re-registering the
same email is rejected.

### B3 — Email-only ☐
**Steps:** sim with auth *email only*. Portal → enter an email, leave password blank
→ Sign in.
**Expected:** a student account is auto-created and you're signed in.

### B4 — Class whitelist ☐
**Steps:** dashboard → **Students** → expand *Add to class list* → paste two emails
→ Add. Then try registering a non-listed email.
**Expected:** non-listed email is refused (403); a listed email registers.

### B5 — Password reset ☐
**Steps:** Portal → request reset (or dashboard **Students** → reset). Without SMTP
configured the reset code is returned in the response.
**Expected:** resetting with the code lets the student log in with the new password.

---

## C. Safe Mode (minors)

### C1 — Minors bundle applied ☐
**Steps:** create a sim with audience **minors** (e.g. `examples/technova/company.yaml`).
**Expected:** auth is forced to shared password; chatbots are keyword-only; every
generated page shows a **privacy notice**; the dashboard shows a green
*"minors-safe — no overrides"* badge.

### C2 — Override banner ☐
**Steps:** create a minors sim whose YAML has `audience_overrides: [llm_chatbots]`
and `chatbot_mode: llm`.
**Expected:** the dashboard shows a **persistent ⚠ banner** listing the non-default
setting; `GET /api/v1/simulations/{id}/audience` returns `safe: false`.

### C3 — Provisioning refused for minors ☐
**Steps:** on a plain minors sim, click **Provision chatbots** (button is hidden;
or call the endpoint).
**Expected:** refused with a minors message (unless `llm_chatbots` is acknowledged).

---

## D. Chatbots & booking

### D1 — Keyword chatbot ☐
**Steps:** open an employee page on any built site → ask a question matching their
knowledge.
**Expected:** a deterministic, in-character answer; no network calls.

### D2 — Provision LLM chatbots (dry-run) ☐
**Steps:** adults sim → **Provision chatbots** (no AnythingLLM configured).
**Expected:** result reports `dry-run`, N provisioned; employees switch to LLM mode
with placeholder embed ids (chat won't answer without a real AnythingLLM).

### D3 — Booking + booking-gated chat ☐
**Steps:** sim with `platform.booking_enabled: true` and
`chatbot_requires_booking: true`; open an employee page on the **served** site
(`/sims/<slug>/...`).
**Expected:** the chat is gated behind a "Book an appointment" panel; picking a slot
and booking unlocks the chat once the slot time has passed. Bookings appear under
dashboard **Bookings**.

---

## E. Visibility rules

### E1 — Hide content now ☐
**Steps:** `POST /api/v1/simulations/{id}/visibility {target_type:"document",
target_id:"x", action:"hide"}`. Then `GET /api/v1/sims/{slug}/visibility`.
**Expected:** the target appears in `hidden`. A future-dated `datetime` rule does
**not** hide until its time passes.

---

## F. Multi-site & the student journey (the big one)

### F0 — Build a multi-site site ☐
**Steps:** `uv run ensayo generate -c examples/workready-mini/simulation.yaml -o ./ms`
→ serve `./ms/dist`.
**Expected:** a **portal** (company cards + "open roles"), a **/jobs/** board (3
roles, filterable), and two company sites each in a different theme.

### F1 — Workflow-driven journey ☐
*Create a workflow-enabled sim via the API (the runtime needs a DB sim with a
workflow):*
```bash
TOKEN=… # from POST /api/v1/auth/login
curl -s -X POST localhost:8000/api/v1/simulations -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"name":"Internship Test",
   "company_yaml":"company:\n  name: Flow Co\nemployees:\n  - {name: Ada Byron, role: Manager, archetype: founder_ceo}",
   "auth_mode":"individual_account","workflow":"internship","build":false}'
```
Then in the **portal** (slug `flow-co`): register → **Apply**.
**Expected:** an application appears at stage *application*; the inbox shows a
"submit your application" message.

### F2 — Interview advances the workflow ☐
**Steps:** (instructor/system) advance the application past *application_submitted*
to *interview*, then in the portal start an **Interview** conversation with the
persona, exchange a couple of messages, and **Finish**.
**Expected:** the conversation is assessed; on a pass the application **advances to
placement on its own**, and a result message lands in the inbox.

### F3 — Submit work ☐
**Steps:** at the placement stage, submit a document via the portal.
**Expected:** it's assessed; a passing submission advances the application; feedback
is shown (or "under review" if a review delay is set).

### F4 — Group chat ☐
**Steps:** start a group chat (occasion + participants + beats) via the portal/API.
**Expected:** the system intro + character beats appear (lazily over time); your
posts interleave; completing it produces a participation note.

---

## G. Management & export (UC)

### G1 — Roster & metrics ☐
**Steps:** dashboard → **Students**.
**Expected:** roster with status, sign-in activity, and booking counts; metrics
summary; **Download CSV** works.

### G2 — Soft delete ☐
**Steps:** delete a student from the roster.
**Expected:** the row remains but shows *deleted* with email redacted; their
bookings are anonymised.

### G3 — Exports ☐
**Steps:** `GET /api/v1/simulations/{id}/export/{applications|conversations|cohort|
journey/{student_id}}`.
**Expected:** each returns JSON with `schema_version: "1.0"` and the expected data.

---

## H. Deployment & CLI

### H1 — Zero-config Docker ☐
**Steps:** `docker compose up -d` → open the mapped port.
**Expected:** the demo simulation is served immediately; dashboard at `/admin/`.

### H2 — CLI ☐
**Steps:** `ensayo validate -c …`, `ensayo list`, `ensayo generate -c … -o out`,
`ensayo workflow run -w internship -e "application_submitted,interview_result:pass,tasks_complete,exit_complete"`.
**Expected:** validate passes; list shows 8 themes; generate builds a site; the
workflow trace ends at *complete*.

---

## Known gaps to be aware of while testing

- **Workflow selection isn't in the dashboard wizard yet** — set `workflow` via the
  API/CLI (scenario F1). The static multi-site `simulation.yaml` carries `workflow`,
  but the *runtime* application state lives in a DB sim.
- **Multi-site creation is CLI-only** (no dashboard "new multi-site" screen).
- **LLM/AnythingLLM** features show stub/dry-run output unless real providers are
  configured.
- **Publish** needs a GitHub repo + `GITHUB_TOKEN`; otherwise it reports the missing
  config rather than pushing.
- **Group-chat `@mention` rescheduling** is not implemented (beats are pre-planned).

Found a bug? File it at <https://github.com/michael-borck/ensayo/issues>.
