# WorkReady — Implementation Plan

**Last updated:** 2026-04-09

## Overview

WorkReady is an AI-powered internship simulation covering six stages of the
intern journey. Students experience the full arc — from browsing a job board
through to an exit interview — before their real placement begins.

Designed for classes of 1,000+ students across 6 fictional WA companies.

---

## What's Built (Streams A, B, C, D pre-hire) — DONE

| Component | Status | URL |
|-----------|--------|-----|
| 6 company websites (ensayo) | Live | `https://{company}.eduserver.au` |
| Interactive fiction primer (Ink) | Live | `https://primer.eduserver.au` |
| seek.jobs (Seek clone) | Live | `https://seekjobs.eduserver.au` |
| WorkReady portal (pre-hire) | Live | `https://workready.eduserver.au` |
| Simulation API (FastAPI) | Live on VPS | `https://workready-api.eduserver.au` |

### Company Sites

| Company | Sector | Theme | URL |
|---------|--------|-------|-----|
| NexusPoint Systems | Technology | tech-dark / sidebar | nexuspointsystems.eduserver.au |
| IronVale Resources | Mining | industrial-red / centered | ironvaleresources.eduserver.au |
| Meridian Advisory | Consulting | corporate-blue | meridianadvisory.eduserver.au |
| Metro Council WA | Government | civic-green / banner | metrocouncilwa.eduserver.au |
| Southern Cross Financial | Finance | finance-slate | southerncrossfinancial.eduserver.au |
| Horizon Foundation | Not-for-profit | warm-hospitality | horizonfoundation.eduserver.au |

Each site has: 5-7 AI employees with backstories, 5 internal documents,
4-5 job postings with careers pages and resume submission forms, chatbot
prompt files. 27 total job postings across 6 companies.

### Simulation API

- **Container:** `ghcr.io/michael-borck/workready-api:latest`
- **Docker Compose:** with `./data` volume for SQLite persistence
- **LLM providers:** stub (dev), Ollama (local/remote with bearer auth),
  Anthropic, OpenRouter
- **Endpoints (live):**
  - `GET /health`
  - `POST /api/v1/resume` — Stage 2 submission with feedback + inbox messages
  - `GET /api/v1/student/{email}/state` — portal state machine + welcome email on first sign-in
  - `GET /api/v1/student/{email}` — full application history
  - `GET /api/v1/application/{id}` — application detail with stage results
  - `GET /api/v1/inbox/{email}?inbox=personal|work`
  - `POST /api/v1/inbox/message/{id}/read`

### Portal — Pre-hire State (DONE)

- Single-page state machine: NOT_APPLIED → APPLIED → HIRED → COMPLETED
- Email-only sign-in (auto-creates student + sends welcome email on first sign-in)
- Personal inbox with read/unread tracking
- Primer runs in main content area (not modal) — sidebar nav stays visible
- "seek.jobs" link opens in new tab (external)
- State badge with hover tooltip
- Locked layout (no width shift between views)
- Theme system ready for company colour switching on hire
- **Database:** students → applications → stage_results (per-stage scores,
  feedback, attempts)

---

## The Student Journey

```
┌─────────────────────────────────────────────────────────────┐
│  LANDING PAGE                                               │
│  • Welcome to WorkReady                                     │
│  • Play the primer (Ink interactive fiction)                 │
│  • Link to WorkReady Jobs                                   │
│  • Personal inbox (application status updates)              │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1: JOB BOARD (WorkReady Jobs)                        │
│  • Browse 27 jobs across 6 companies                        │
│  • Filter by sector, type, company                          │
│  • "Apply on Company Site" or "Quick Apply" (via Seek)      │
│  • Explore company websites (ensayo sites)                  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  STAGE 2: RESUME SUBMISSION                                 │
│  • Apply via company careers page or WorkReady Jobs         │
│  • Upload PDF resume + cover letter                         │
│  • Page shows: "Application received"                       │
│  • Hours later: email to personal inbox with outcome        │
│  • If unsuccessful: feedback + try another role             │
│  • If successful: interview invitation                      │
└─────────────────┬───────────────────────────────────────────┘
                  │ (hired)
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  PORTAL — "Your Workstation"                                │
│  Themed to match the company (same ensayo theme/branding)   │
│  • Dashboard (current stage, upcoming tasks)                │
│  • Work inbox (messages from manager, HR, colleagues)       │
│  • Task workspace (briefs, documents, submissions)          │
│  • Team view (intake colleagues — real students + AI)       │
│  • Company intranet (link to ensayo site)                   │
│  • Job board link deactivated                               │
│                                                             │
│  STAGE 3: Interview (AI hiring manager conversation)        │
│  STAGE 4: Work task (brief → draft → feedback → submit)     │
│  STAGE 5: Social moment (lunchroom scenario)                │
│  STAGE 6: Exit interview (reflection + final feedback)      │
└─────────────────────────────────────────────────────────────┘
```

---

## Scaling: Cohorts Within Companies

1,000+ students across 6 companies = ~170 per company. They can't all
compete for the same jobs. Solution: **intake cohorts.**

Each company runs multiple intakes of 8-10 students, each assigned to
a department/team. Students in the same intake can see each other.

```
NexusPoint Systems
  ├── Intake 1 (Cybersecurity team) — 8 students, reporting to Marcus Webb
  ├── Intake 2 (Service Delivery) — 8 students, reporting to Priya Sharma
  ├── Intake 3 (Solutions Architecture) — 8 students, reporting to Liam Foster
  └── ... (as many intakes as needed)
```

Each intake gets:
- One job posting (from the company's pool)
- One hiring manager (AI character — the employee the job reports to)
- One mentor (AI character — a colleague in the same team)
- Colleagues: mix of AI characters + real students in the same intake
- A unique work task appropriate to the department

Jobs never "run out" — the system opens new intakes. Every student gets
a position.

---

## Stream D — Student Portal (next build)

The portal is the single web app that serves as the student's WorkReady
experience throughout the simulation. There is **no separate landing
page** — the portal itself transforms based on the student's state.

### D1. Single-Page State Machine

The student visits one URL throughout the entire simulation. The page
queries the API for their state and renders different sections accordingly.
This mirrors reality (you don't change websites when you start a job)
and preserves continuity (you can always look back at your application
history).

**State progression:**

```
NOT_AUTHENTICATED
    │
    ▼  (enters email)
NOT_APPLIED
    • Welcome banner
    • Play the Primer button
    • Browse WorkReady Jobs button
    • Personal inbox (empty)
    │
    ▼  (submits application via company site or Seek clone)
APPLIED_AWAITING_OUTCOME
    • Status: "Application under review"
    • Browse more jobs
    • Personal inbox: "Application received" message
    │
    ▼  (delayed feedback delivered)
APPLICATION_OUTCOME
    • Personal inbox: "Interview invitation" or "Unsuccessful" message
    • If unsuccessful → return to job browsing, that company off the board
    • If successful → "Accept invitation" button activates Stage 3
    │
    ▼  (interview completed and passed)
HIRED
    • Theme switches to assigned company's CSS variables
    • Welcome banner: "Welcome to {Company Name}"
    • Dashboard, Tasks, Work inbox, Team view, Company intranet
    • Job board link greyed out
    • Personal inbox still accessible (history preserved)
    • Work inbox active
    │
    ▼  (Stages 4, 5, 6 complete)
COMPLETED
    • Internship complete banner
    • Final reflection + readiness score
    • Replay option (browse other companies)
```

### D2. Sections (visibility depends on state)

Always visible:
- **Header** with student name and current state indicator
- **Personal inbox** (status updates, application correspondence)

Visible when NOT_APPLIED or APPLIED:
- **Primer link** (play the Ink interactive fiction)
- **Job board link** (WorkReady Jobs)
- **Application history** (jobs you've applied to and outcomes)

Visible when HIRED or COMPLETED:
- **Dashboard:** Current stage, progress bar, upcoming deadlines
- **Work inbox:** Messages from AI manager, mentor, HR, colleagues
- **Task workspace:** Briefs, documents, submissions, feedback
- **Team view:** Intake colleagues (real students + AI characters)
- **Company intranet link:** to the company's ensayo site
- **Mentor chat:** always-available AI mentor

### D3. Theming — Single CSS, Multiple Personalities

The portal has one HTML/CSS codebase. When a student is hired, the page
injects CSS variables matching their assigned company's theme:

```javascript
document.documentElement.style.setProperty('--sim-primary', site.branding.primary);
document.documentElement.style.setProperty('--sim-accent', site.branding.accent);
// etc.
```

A student at IronVale sees industrial-red styling. A student at Meridian
Advisory sees corporate-blue. Same codebase, different identity.

The pre-hire state uses a neutral WorkReady theme (the platform's own
brand, not a company's).

### D4. Authentication

For MVP: email-only "sign in" — student enters their email and the API
looks up their state. No password.

For production: Curtin SSO integration (later phase).

### D5. Tech

- Vanilla JS or minimal framework (the complexity is in the API)
- Single repo: `workready-portal`
- Hosted on GitHub Pages
- All state from the WorkReady API

### D6. Email Simulation

Two inboxes, reflecting real workplace separation:

**Personal inbox (landing page):**
- Application confirmations ("We received your application for...")
- Interview invitations ("We'd like to invite you to interview for...")
- Offer / rejection ("Congratulations..." / "Thank you for your interest...")
- Timing: delayed delivery (configurable — hours or next day)

**Work inbox (portal):**
- Welcome message from HR on first login
- Task brief from manager ("Hi [name], welcome to the team...")
- Mentor check-ins ("How's the project going? Need any help?")
- Colleague messages (AI-generated workplace chat)
- Meeting invitations, feedback notifications
- Timing: triggered at stage transitions and milestone dates

Messages are stored in the API database and delivered via the portal
UI. No actual email sending — avoids institutional IT dependencies.

---

## Architecture Foundations (decided 2026-04-10)

These decisions shape everything else and were made before Stage 3
implementation to avoid retrofit work later.

### Headless / API-first architecture

The WorkReady ecosystem follows a "smart backend, dumb frontends" model:

- **API** holds all business logic, state, scoring, persistence, LLM calls
- **Frontends** are pure presentation — static HTML/CSS/JS that fetches
  from the API
- **Multiple frontends share one API** — portal, seek.jobs, company sites,
  future mobile apps
- **API is versioned** (`/api/v1/`) so breaking changes ship as `/api/v2/`
  alongside the existing version
- **Frontends are disposable** — redesign without touching the backend

Benefits: testability, single source of truth, smarts protected on the
server, easy to add new clients (e.g. mobile app, lecturer dashboard).

### Identity model — internal student IDs

`student_email` is **not** the primary key. Each student has an internal
`student_id` (integer) and email is a property that can change.

```sql
CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

All foreign keys reference `student_id`. Lookups by email still work,
but the canonical identifier is the integer ID. This makes email changes
safe (just update the email column), and supports future SSO migration
where the student's identity might come from Curtin Azure AD.

### Notification adapter pattern

The API never directly calls "send a message via X". It calls a single
`notify()` function that decides which channels to use based on:
- The event type (some always go to specific channels — e.g. interview
  invitations always go to email AND in-app)
- The student's preferences (which channels they've opted into)
- The cohort's policy (some cohorts use Discord, others use email only)

```python
notify(
    student_id=42,
    event="interview_invitation",
    content={"job_title": "...", "company": "...", "feedback": {...}},
    channels="auto",  # or explicit ["in_app", "email"]
)
```

The adapter dispatches to registered channel handlers. Adding a new
channel = writing one adapter and registering it. The calling code
never changes.

**MVP channels:** in-app inbox only.
**Phase 2:** + real email (Postmark or SES)
**Phase 3:** + Telegram bot
**Phase 4:** + MS Teams (Curtin institutional integration)

Channels intentionally **not** prioritised:
- WhatsApp — privacy concerns and per-message cost at scale
- Discord — great for ≤50 student pilots, doesn't scale to 1,000 cleanly
- SMS — cost vs value not justified

### Communications channel comparison

| Channel | Setup | Cost | Scale | Best for | Worst for |
|---------|-------|------|-------|----------|-----------|
| In-app inbox | Built | $0 | ∞ | Anything in-portal | Outside portal |
| Real email | Low | ~$0 | ∞ | Async, formal | Real-time chat |
| Telegram bot | Low | $0 | ∞ | Async chat, alerts | Group dynamics |
| MS Teams | High (IT approval) | $0 | ∞ | Institutional | Build complexity |
| Discord | Medium (multi-server) | $0 | ~500 ch/server | Small social cohorts | Large scale |
| WhatsApp Business | High | ~$0.005/msg | $$$ | WA-dominant demographics | Cost |
| SMS (Twilio) | Low | ~$0.05/msg | $$$$ | Critical alerts only | Substantial messaging |

### Multi-stage interview pipelines (data model now, MVP single-stage)

Real hiring is rarely one conversation. WorkReady supports configurable
interview pipelines per job from day one in the data model, even if
MVP fills in only single-stage:

```yaml
# In brief.yaml
jobs:
  - title: "Junior Security Analyst"
    interview_pipeline:
      - type: "manager"
        with: "marcus-webb"

  - title: "Senior Cloud Engineer"
    interview_pipeline:
      - type: "hr_screen"
        with: "jordan-reeves"
        duration_min: 15
      - type: "technical"
        with: "liam-foster"
        format: "scenario_discussion"
      - type: "panel"
        with: ["alex-nguyen", "marcus-webb"]
```

The simulation API tracks `current_interview_stage` within Stage 3.
The portal shows progress: "Interview 1 of 3 — HR Screen with Jordan
Reeves." Each sub-interview can have its own format and assessor.

For MVP, every job has a single-step pipeline `[manager]`. We can
fill in multi-stage for technical roles in a later iteration without
schema changes.

**Future interview formats** (Phase 2+):
- `scenario_discussion` — chat-based "walk me through how you'd..."
- `github_review` — submit a repo URL, AI fetches and reviews code
- `live_code` — Monaco editor in portal, AI evaluates output
- `take_home` — written assignment with submission and feedback

### Authentication strategy

**MVP:** Email-only "sign in" — student enters email, API trusts them
(no verification). Stored in localStorage. Sufficient for testing and
the educational simulation context.

**Phase 2:** Passwordless authentication with magic codes:
1. User enters email
2. API generates a 6-digit code, stores with 10-min TTL
3. API emails the code (via the same notification adapter)
4. User enters the code
5. API verifies, issues a JWT (30-day expiry)
6. Token in localStorage, sent as `Authorization: Bearer <token>`
7. All API endpoints verify the token, extract `student_id`

Benefits over passwords:
- No passwords to forget, manage, or compromise
- Email verification is built into the login flow
- Migration path for Curtin SSO later (Azure AD → JWT exchange)
- Recovery is just "request a new code"

**Phase 3+:** Curtin SSO integration via Azure AD.

### Backend protection (Phase 2 priorities)

- **Rate limiting** via `slowapi` — per-IP and per-token limits, critical
  on LLM endpoints (cost protection) and auth endpoints (brute-force
  protection)
- **Per-cohort LLM budget** — runaway cohort can't burn other cohorts'
  tokens
- **HMAC-signed webhook endpoints** — for inbound email when added
- **Audit log** of admin actions
- **Content security policy** headers
- **CSRF tokens** if cookie-based auth is added later

### Pre-Stage 3 refactors (small but load-bearing)

Three small refactors before building Stage 3, to avoid retrofit cost:

1. **Notification adapter** — wrap `create_message()` in `notify()`.
   ~1 hour. Today only does in-app, but the abstraction is in place.
2. **Internal student_id** — migration from `student_email` as PK to
   `student_id` integer with email as a unique column. ~2 hours.
3. **Multi-stage interview data model** — `interview_pipeline` field on
   job specs and `current_interview_stage` on applications. MVP fills
   in single-stage only. ~30 minutes of design.

Total: ~half a day, saves weeks of refactoring later.

---

## Stream E — Stages 3-6 (detailed design)

### Stage 3: Interview (NEXT BUILD)

**What:** Guided AI conversation with the hiring manager character (the
employee named in `reports_to` on the job posting). The student talks to
a real character — Marcus Webb at NexusPoint, Karen Whitfield at IronVale,
etc. — using the chatbot prompt that ensayo already generated for them.

#### Decisions

| Question | Decision |
|----------|----------|
| Turn limit | **Soft (~10 exchanges)** — feels natural, AI wraps up when ready |
| Retries | **No** — failed interview puts that company off the board for that student |
| Transcript visibility | **Yes** — student can review the full conversation later |
| Tone of failure feedback | **Firm but constructive** — clear no-progress, actionable suggestions |
| Feedback delivery | **Both in-app and via personal inbox** — students get a permanent record |

#### Conversation flow (guided phases)

The system prompt steers the AI through these phases naturally — the
conversation feels real, not scripted:

1. **Welcome / icebreaker** ("Tell me a bit about yourself")
2. **Background / motivation** ("What drew you to {Company}?")
3. **Role-specific questions** (about the actual job duties)
4. **Behavioural questions** ("Tell me about a time when...")
5. **Candidate's questions** ("Do you have any questions for me?")
6. **Close** ("Thanks, we'll be in touch")

The AI is told it has approximately 10 exchanges, after turn 8 it should
be wrapping up. Either side can end early — student has an "End interview"
button.

#### Adaptation based on Stage 2

Each interview is seeded with:
- The student's resume score (high score → confident interviewer; low
  score → more probing questions)
- The student's cover letter text
- The full job description
- The company scenario and tensions
- The hiring manager's full character prompt

#### Scoring

Same structured format as resume assessment, plus interview-specific
dimensions:

```json
{
  "fit_score": 72,
  "dimensions": {
    "communication": 80,
    "preparation": 65,
    "cultural_fit": 75,
    "role_awareness": 70,
    "asked_good_questions": true
  },
  "strengths": ["..."],
  "gaps": ["..."],
  "suggestions": ["..."],
  "proceed_to_role": true,
  "summary": "..."
}
```

#### Outcome paths

- **Pass:** `application.status` stays `active`, `current_stage` advances
  to `work_task`, portal switches to HIRED state with company theme,
  inbox gets "Welcome to {Company}" message
- **Fail:** `application.status` set to `rejected`, company added to
  blocked list, inbox gets "Update on your application" message with
  full feedback, portal returns to NOT_APPLIED state with the failed
  company greyed out on seek.jobs

#### "Off the board" — how it works

The current seek.jobs is a static site that doesn't know who's logged in.
To make companies disappear/grey out for a specific student, several
changes are needed:

**Database:**
- Add `status` column to `applications` table:
  `active` | `rejected` | `hired` | `completed`
- Resume failure → `rejected`. Interview failure → `rejected`.
  Hired → stays `active` until completion.

**API extension:**
- Extend `StudentState` response with a `blocked_companies` field
  (list of company slugs the student has had a rejected application at)

**seek.jobs becomes API-aware:**
- Currently fully static. Needs to:
  1. Read student email from URL query parameter (passed when portal
     links to it: `https://seekjobs.eduserver.au/?student=jane@curtin.edu.au`)
  2. Cache email in seek.jobs' own `localStorage`
  3. On page load, fetch `/api/v1/student/{email}/state` to get
     blocked companies and current applications
  4. Grey out (don't hide) jobs from blocked companies — students
     should see the consequences of their failed applications
  5. If currently hired/in-progress, all jobs show as "you're already
     employed elsewhere" or similar
  6. If no email param and no localStorage, show all jobs in browse mode

The portal's "Browse seek.jobs" button is updated to append the email
query parameter, so seamless single sign-in across both apps.

#### Feedback in the personal inbox

Both Stage 2 (resume) and Stage 3 (interview) outcome messages will
include the structured feedback inline as formatted plain text. This
gives students a permanent record they can re-read.

For interviews specifically, the inbox message includes a "View full
transcript" link that opens the conversation in a modal — separating
the formal feedback from the reflective transcript.

This **also applies retroactively to Stage 2** — the current resume
outcome messages just say "we received your application" / "we're not
progressing". They should include the actual feedback (strengths, gaps,
suggestions, tailoring) so students have something to learn from.

#### API additions

```
POST /api/v1/interview/start
  Body: { application_id }
  Response: { session_id, manager_name, manager_role, company_name,
              opening_message, max_turns }

POST /api/v1/interview/message
  Body: { session_id, message }
  Response: { reply, turn, max_turns, suggested_wrap_up }

POST /api/v1/interview/end
  Body: { session_id }
  Response: { assessment, proceed_to_role, message }

GET /api/v1/interview/{session_id}/transcript
  Response: { messages: [...], assessment, manager_name, ... }
```

#### New table

```sql
CREATE TABLE interview_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    manager_slug TEXT NOT NULL,
    manager_name TEXT NOT NULL,
    transcript_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'active',
    final_score INTEGER,
    feedback_json TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
```

#### Schema migration

```sql
ALTER TABLE applications ADD COLUMN status TEXT DEFAULT 'active';
-- Backfill: existing apps with current_stage in (interview, work_task,
-- lunchroom, exit_interview, completed) are 'active' or 'completed'.
-- Apps stuck at 'resume' with a failed stage_result are 'rejected'.
```

#### Portal additions

- New `interview` view in main content area (chat-style)
- Detected by checking `state.active_application.current_stage === 'interview'`
- Manager card at top (name, role, company, themed colours)
- Message bubbles, text input, turn indicator
- "End interview" button (with confirmation)
- After completion: feedback panel + button to continue or return to job board
- Feedback is shown inline AND copied to personal inbox

#### Build order for Stage 3

1. **API**: schema migration + interview_sessions table + LLM prompt design
2. **API**: start/message/end endpoints (using existing LLM provider config)
3. **API**: extend StudentState with `blocked_companies`
4. **API**: enhance Stage 2 outcome messages with full feedback (retroactive fix)
5. **Portal**: chat view with message bubbles
6. **Portal**: state detection — show interview view when
   `current_stage === 'interview'`
7. **Portal**: feedback display + transcript modal
8. **seek.jobs**: become API-aware (read email, fetch blocked list, grey out)
9. **Portal**: update "Browse seek.jobs" link to pass email query param

### Stage 6: Exit Interview

**Same tech as Stage 3**, different prompt focus:

- Reflection on the internship experience (Stages 4-5)
- How they handled feedback
- What they learned
- Professional goal-setting
- Graceful close — "leaving a positive final impression"

**Scoring:** Self-awareness, communication, professionalism, growth mindset.

### Stage 4: Work Task

**What:** Students receive a realistic work task, complete it over 2-3 weeks
with mentor support and iterative feedback.

**Task content system:** Extend ensayo to generate work tasks per department:

```yaml
# In brief.yaml
tasks:
  - department: "Cybersecurity"
    title: "Client Security Assessment Report"
    brief: "Conduct a vulnerability assessment of a client network diagram
            and write a findings report with recommendations"
    deliverable: "PDF report (2000-3000 words)"
    duration_weeks: 3
    milestones:
      - week: 1
        name: "Scope and approach"
        description: "Submit your assessment plan and methodology"
      - week: 2
        name: "Draft findings"
        description: "Submit draft report for mentor review"
      - week: 3
        name: "Final report"
        description: "Submit polished report incorporating feedback"
```

**Milestone workflow:**
1. Task brief delivered to work inbox (Week 0)
2. Milestone 1 due → student submits → mentor AI gives formative feedback
3. Milestone 2 due → student submits draft → mentor AI gives detailed feedback
4. Final submission → manager AI gives summative assessment
5. Score recorded, advance to Stage 5

**Mentor AI:** Available throughout via chat. Students who ask good questions,
show their working, and iterate get better feedback. Students who submit
without engaging get realistic "this needs more work" responses.

The mentor is the key pedagogical tool — it teaches that *asking for help
is a professional skill, not a weakness.*

**Company documents:** Students access the company's ensayo site documents
as "internal resources" to inform their work. The cybersecurity intern reads
the Information Security Policy. The finance intern reads the financial
planning process guide. This is why the documents exist.

**API:**
`POST /api/v1/task/submit` → upload milestone/final deliverable
`GET /api/v1/task/{application_id}` → current task, milestones, feedback
`POST /api/v1/mentor/message` → chat with mentor AI

### Stage 5: Social Moment

**What:** An unscripted workplace social situation. Tests reading the room,
belonging, navigating informal culture.

**Design:** AI-driven scenario, not a live interaction (for scale).

**Implementation:** A contextual chat/narrative scene:

- Setting: described in text ("You walk into the break room. Three colleagues
  are gathered around a cake. Someone you haven't met is telling a story
  about the weekend.")
- Multiple AI characters present, each with personality
- Student gets dialogue options + free-text responses
- The scene unfolds based on choices — 5-10 minutes
- Scoring: social awareness, authenticity, engagement

**Could use:**
- Ink-style branching narrative (like the primer, but in-portal)
- Multi-character chat interface (student talks, AI characters respond
  naturally as a group)
- Combination: narrative framing with chat interaction

**What's scored:**
- Did they engage or avoid?
- Did they read the room correctly?
- Were they authentic vs. performative?
- Did they remember colleague names / show interest?

**Outcome:** No pass/fail — this is formative. Feedback delivered in
the exit interview (Stage 6), where the manager references the moment:
"I noticed you joined the birthday celebration — Sarah appreciated that"
or "The team mentioned they didn't see much of you socially."

---

## WorkReady Jobs Enhancements

### HR Agency Cross-listings (not yet built)

Some jobs appear twice on WorkReady Jobs: once from the company directly,
once from a fictional recruitment agency with different wording.

**Agencies:**
- PerthTalent Recruitment
- WestForce Staffing
- Catalyst People Solutions

**Implementation:** The build script generates variant listings with
AI-rewritten descriptions. The company_slug stays the same (same apply
endpoint), but the listed employer shows the agency name.

This teaches students that the same role appears differently depending
on who's advertising it — a real-world phenomenon.

### Apply Flow

Real Seek supports both routes:
- **"Quick Apply"** — submit through Seek directly (hits the API with
  `source: "seek"`)
- **"Apply on company site"** — redirects to the company's careers page
  (hits the API with `source: "direct"`)

Both should work in WorkReady Jobs. The API records the source for
analytics (do students who apply directly perform differently?).

---

## Communication Layer

### What to build now

- **Simulated email (in-app inbox):** Personal inbox (landing page) +
  work inbox (portal). All messages stored in API, delivered via UI.
  No actual email sending.

### What to add later

- **LinkedIn integration (optional activity):** Students create/update
  LinkedIn profiles, post about their "internship." Not system-assessed —
  it's a parallel professional development activity. Mentioned in the
  unit guide, not enforced by the platform.

- **Discord (for social/informal):** Could serve as the Stage 5
  "lunchroom" channel for small cohorts. AI character bots in Discord
  are well-supported. Works for classes of 30-50, not 1,000.

- **MS Teams integration (Phase 3):** Curtin is an MS shop. Teams
  integration would add professional communication skills (Teams
  etiquette, meeting scheduling). Requires institutional approval
  and significant integration work. Valuable but not MVP.

---

## Build Priority (Streams D & E)

| Priority | What | Status |
|----------|------|--------|
| 1 | Portal shell — single page, state machine, email auth, personal inbox | DONE |
| 2 | Inbox API endpoints — fetch/mark messages, trigger on stage transitions | DONE |
| 3 | Welcome email on first sign-in | DONE |
| 4 | Schema migration: applications.status, interview_sessions table | DONE |
| 5 | Stage 2 outcome messages include full feedback (retroactive fix) | DONE |
| 6 | blocked_companies in StudentState | DONE |
| 7 | **Notification adapter** — wrap create_message in notify() | NEXT (pre-S3) |
| 8 | **Internal student_id** — schema migration, email as property | NEXT (pre-S3) |
| 9 | **Multi-stage interview data model** — interview_pipeline support | NEXT (pre-S3) |
| 10 | **Interview endpoint** (Stage 3) + chat UI in portal | After refactors |
| 11 | seek.jobs becomes API-aware — grey out blocked companies | With Stage 3 |
| 12 | **Hired-state portal** — theme switching, dashboard, work inbox | After Stage 3 |
| 13 | **Task content system** in ensayo (task briefs + rubrics) | Stage 4 content |
| 14 | **Task submission + mentor chat** (Stage 4) | Core work simulation |
| 15 | **Social scenario** (Stage 5) | Workplace culture simulation |
| 16 | **Exit interview** (Stage 6) | Closing the loop |
| 17 | HR agency cross-listings on job board | Realism enhancement |
| 18 | Cohort/intake management in API | Scaling to 1,000+ |
| 19 | Delayed email delivery (timed message release) | Authentic pacing |
| 20 | Real email sending (Postmark/SES) via notification adapter | Phase 2 |
| 21 | Passwordless auth with magic codes | Phase 2 |
| 22 | Rate limiting and per-cohort LLM budgets | Phase 2 |
| 23 | Inbound email (replies via webhook) | Phase 2 |
| 24 | Telegram bot adapter | Phase 3 |
| 25 | LMS integration (Blackboard/Canvas SSO + grade pass-back) | Phase 3 |
| 26 | MS Teams integration via Graph API | Phase 4 |

---

## Technical Architecture

```
                    ┌──────────────────┐
                    │   Landing Page   │
                    │  (static site)   │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
    ┌─────────────┐  ┌────────────┐  ┌───────────┐
    │   Primer    │  │ WorkReady  │  │  Company  │
    │   (Ink)     │  │   Jobs     │  │  Sites ×6 │
    │             │  │(Seek clone)│  │  (ensayo)  │
    └─────────────┘  └─────┬──────┘  └─────┬─────┘
                           │               │
                           └───────┬───────┘
                                   ▼
                    ┌──────────────────────────┐
                    │    WorkReady API          │
                    │    (FastAPI + SQLite)     │
                    │                          │
                    │  /api/v1/resume     (S2)  │
                    │  /api/v1/interview  (S3)  │
                    │  /api/v1/task       (S4)  │
                    │  /api/v1/social     (S5)  │
                    │  /api/v1/exit       (S6)  │
                    │  /api/v1/inbox            │
                    │  /api/v1/student          │
                    └──────────┬───────────────┘
                               │
                    ┌──────────▼───────────────┐
                    │     Student Portal       │
                    │  (themed per company)     │
                    │                          │
                    │  Dashboard               │
                    │  Work inbox              │
                    │  Task workspace          │
                    │  Team view               │
                    │  Mentor chat             │
                    └──────────────────────────┘
```

---

## Repositories

| Repo | Purpose |
|------|---------|
| `ensayo` | Site generator (tool) |
| `nexuspoint-systems` | Company site |
| `ironvale-resources` | Company site |
| `meridian-advisory` | Company site |
| `metro-council-wa` | Company site |
| `southern-cross-financial` | Company site |
| `horizon-foundation` | Company site |
| `workready-jobs` | Seek clone (static site) |
| `workready-api` | Simulation backend (Docker) |
| `workready-primer` | Interactive fiction (Ink) |
| `workready-portal` | Single-page student portal — pre-hire AND post-hire (not yet built) |

---

## Timeline Alignment with Proposal

| Proposal Phase | WorkReady Streams | Status |
|---------------|-------------------|--------|
| Phase 1: Primer (4-6 weeks) | Stream B | DONE |
| Phase 2: Core Simulation | Streams A, C, D, E | A+C done, D+E next |
| Phase 3: Integration & Expansion | Cohort mgmt, LMS, Teams | Future |
