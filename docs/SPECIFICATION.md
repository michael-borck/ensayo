# Ensayo — Platform Specification

**Version:** 2.0-draft
**Date:** 2026-05-06
**Status:** Pre-implementation design document
**Audience:** Developers and architects

---

## What changed from v1

This is a substantial revision following a design review. The major changes:

- **One deployment model.** The previous "static vs self-hosted" framing is dropped. Ensayo always runs as a VPS-hosted FastAPI service that pushes generated static sites to GitHub. There is no purely static deployment.
- **YAML-canonical, DB-cache.** The dual source-of-truth ambiguity is resolved. YAML in the simulation's git repo is canonical for content; SQLite on the VPS is canonical for runtime state and a rebuildable cache of content.
- **One repo per simulation.** Multi-site simulations use subpaths of a single custom domain. Per-site primary domains are future work.
- **Open self-host.** Ensayo is open source; anyone can deploy a VPS instance. There is no multi-tenant SaaS. Within an instance, multiple UCs can share infrastructure.
- **Base content is baked in at creation.** Base library items are copied into the simulation's YAML when scaffolded, not referenced live. Updating Ensayo upstream does not retroactively change existing simulations.
- **Multi-UC content sharing uses visibility rules, not branches.** Co-coordinators hide unwanted content per unit; modifications require ownership or a clone-to-fork.
- **Safe Mode is a first-class section.** TechNova's "safe for minors" requirement gets its own section with a defaults bundle and override banners.
- **No migration phase.** CloudCore, Pinnacle, and TechNova are reference inspiration only. Ensayo is greenfield; new simulations are built with it from scratch.
- **Workflow engine spike added** before multi-site implementation commits.
- **Name normalised** to "Ensayo" throughout.
- **Deployment patterns from workready-deploy adopted:** zero-config first run as a guarantee (stub LLM + keyword chatbots + path-based Caddy fallback), single `install.sh` as source of truth for bare-metal and Docker, pre-built GHCR image, `domains.env` / `.env` split, CORS in Caddy.
- **Astro-as-theme-engine.** Themes are full Astro packages (own templates, components, scoped CSS), not parameterised Jinja2 templates. Each WorkReady company site becomes a distinct theme. Node is a build-time dependency on the VPS; deployed sites remain pure static HTML on GitHub Pages.
- **Patterns from workready-api absorbed:** notification adapter (pluggable channels), persona prompts as `.txt` files on disk in the repo, idempotent on-startup migrations, per-surface LLM stubs, two-layer configuration (instance env + per-simulation YAML overrides), generic external-tool export endpoints, "what Ensayo deliberately doesn't include" disclosure.
- **Optional interactive primer.** Per-simulation Ink-based interactive fiction at `/primer/` subpath, used for advanced multi-site sims to rehearse the workflow shape before the real run. Phase 8 deliverable; not in MVP.
- **Bulk LLM generation at simulation creation is default ON for adults.** When an LLM provider is configured, the wizard generates all backstories, documents, scenario, and culture in one pass — that's where the platform earns its keep. Cost estimate shown up front. Default OFF for minors-audience simulations (forces per-item review).
- **Save vs Publish edit model.** Save writes YAML locally; Publish commits and pushes to GitHub Pages. UCs can iterate mid-semester without disturbing the live cohort. Optional Auto-publish toggle for solo or pre-cohort work.
- **Soft delete for student data with mutable email.** `student_access.id` is canonical; email is a mutable identifier. Deletion redacts PII and anonymises transcripts but preserves DB integrity. No reactivation — returning students get new identities. Hard-delete admin command for escalated regulatory cases.
- **Observability via structured JSON logs.** Logs to stderr + rotated file. Platform does not include log viewer or alerting — future work is a separate consumer tool. Minors mode logs aggregate only.
- **Theme compatibility is advisory, not blocking.** UC overrides are logged; pattern of overrides signals where the platform should extend theme support.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Reference Analysis](#2-reference-analysis)
3. [Architecture Overview](#3-architecture-overview)
4. [Data Model](#4-data-model)
5. [Deployment Model](#5-deployment-model)
6. [Authentication and Access Control](#6-authentication-and-access-control)
7. [Safe Mode and Audience Configuration](#7-safe-mode-and-audience-configuration)
8. [LLM Provider Abstraction](#8-llm-provider-abstraction)
9. [AnythingLLM Integration](#9-anythingllm-integration)
10. [Instructor (UC) Dashboard](#10-instructor-uc-dashboard)
11. [Student-Facing Simulation](#11-student-facing-simulation)
12. [Multi-Site Simulation](#12-multi-site-simulation)
13. [Document and Content Library](#13-document-and-content-library)
14. [Phased Implementation Roadmap](#14-phased-implementation-roadmap)
15. [Open Questions and Risks](#15-open-questions-and-risks)

---

## 1. Executive Summary

### What Ensayo Is

Ensayo is a configurable, LLM-assisted platform that generates fully functional web-based workplace simulations for university and school teaching. A **simulation** is a fictional organisation (or network of organisations) rendered as a website where students interact with virtual employees (chatbots), read internal documents, book appointments, and complete scenario-driven tasks — all within a safe, controlled environment.

Ensayo produces two kinds of simulation:

- **Single-company** — one fictional organisation with departments, employees, documents, and chat interfaces.
- **Multi-site** — a hub portal coordinating multiple subsidiary or client company sites, each with its own identity, deployed as subpaths of a single custom domain.

Ensayo is **open-source self-hosted**. Anyone — university, school, or individual educator — can deploy their own VPS instance. There is no multi-tenant SaaS; instead, deployers run their own instance and host as many simulations as they need on it.

### Who It Is For

| Role | Responsibility |
|------|---------------|
| **Instance admin** | Deploys Ensayo on a VPS, configures LLM providers, creates UC accounts. May be the same person as the lecturer for a solo educator. |
| **Unit Coordinator (UC) / Lecturer** | Creates and manages simulations through the dashboard. Configures content, manages students, monitors engagement. |
| **Student** | Navigates a generated simulation site, chats with virtual employees, books appointments, reads documents, completes tasks. |

### What Problem It Solves

Today, each simulation (CloudCore, Pinnacle Events, RetailFlow, TechNova, the six WorkReady companies) is built by hand — bespoke HTML, manually written chatbot prompts, individually configured APIs. Creating a new simulation takes weeks. Modifying an existing one requires a developer.

Ensayo replaces this artisanal process with a **configuration-driven generator**: a UC describes their fictional company through a wizard (or in YAML), and the platform produces a complete, deployable simulation. LLM assistance reduces the creative burden of writing employee backstories, policy documents, and scenario narratives.

### Guiding Principles

1. **Configuration over code.** A lecturer should be able to create a new simulation without writing HTML, CSS, or JavaScript.
2. **Generate once, edit forever.** The generator scaffolds the site. After that, content is edited through the dashboard (which writes YAML and pushes to git). The generator is always available to re-scaffold.
3. **Open self-host.** Free, open-source, runs on a $5–20/month VPS. No SaaS, no vendor lock-in, no per-seat fees.
4. **Static sites for students, dynamic API on VPS.** Simulation sites are static HTML on GitHub Pages. Dynamic features (auth, booking, chatbots, dashboard, conversations) live on a single VPS-hosted FastAPI service.
5. **LLM-assisted, not LLM-required.** The platform works without LLM keys (stub mode + keyword chatbots). LLM features enhance content creation and chatbot behaviour but are not required for deployment or evaluation.
6. **Safe by default for sensitive audiences.** A "safe mode" exists for minors and other audiences where LLM output is inappropriate or PII collection is restricted.
7. **Progressive complexity.** A simulation works at every tier — from a local Docker compose with stub LLM, to a production deployment with AnythingLLM and individual student accounts.
8. **Predictable for live cohorts.** Once a simulation is in front of students, the platform avoids surprise updates. Base library changes don't auto-propagate; YAML in the repo is the immutable record.
9. **Zero-config first run.** `docker compose up -d` against the pre-built image produces a working simulation immediately — no DNS, no API keys, no AnythingLLM. Stub LLM, keyword chatbots, and path-based Caddy routing make the first launch demonstrable in minutes. Real LLM, custom domains, and AnythingLLM are opt-in upgrades that don't change the architecture.

---

## 2. Reference Analysis

Ensayo is greenfield. Its design draws lessons from three existing projects, each of which contributes a different pattern.

### 2.1 CloudCore Networks — The Single-Company Pattern

**What it is:** A B2B cloud services company with 47 employees, recovering from a major data breach. Used across 5 teaching units (ISA, ISEC, AI, BWT, MKT).

**Patterns Ensayo carries forward:**

| Pattern | What It Looks Like | Why It Matters |
|---------|-------------------|----------------|
| Deep employee personas | 21 fully developed characters with 2,500-word backstories, personality traits, knowledge areas, and cross-referral maps | Students can interview anyone and get consistent, realistic responses |
| Narrative spine | A single breach event ties all scenarios together — every employee has a perspective on it | Gives the simulation coherence without constraining teaching angles |
| Rich document ecosystem | 31 policies, 13 interview transcripts, 6 CSV datasets, blog posts, incident reports | Students practice real-world information gathering |
| AnythingLLM chatbot integration | Per-employee workspaces with RAG over company documents | Employees answer consistently from company knowledge, not just their persona prompt |
| Instructor dashboard | FastAPI backend managing unit passwords, visibility rules, file uploads, git push-to-deploy | UCs control what students see without touching code |

**What Ensayo does differently:**

| What CloudCore Did | What Ensayo Does |
|-------------------|------------------|
| Quarto site generator (build-step bottleneck, R/Python environment fragility) | Vanilla HTML/CSS/JS via Jinja2 templates — no build step beyond `ensayo generate` |
| `cloudcore-api` knows about one repo only | Dashboard manages many simulations on one VPS |
| Hand-written employee configs in booking API | Generator produces all configs from YAML |
| Booking API exists but isn't wired in | Booking is first-class with frontend gating |

### 2.2 WorkReady — The Multi-Site Pattern

**What it is:** A full internship simulation with a student portal, Seek-style job board, six distinct company sites, AI chatbot employees, and a central FastAPI backend providing API endpoints consumed by static frontends.

**Patterns Ensayo carries forward:**

| Pattern | What It Looks Like | Why It Matters |
|---------|-------------------|----------------|
| Static frontends + central API | Portal, job board, and all 6 company sites are vanilla HTML/JS calling a shared FastAPI backend | Frontends deploy as static; only the API needs a server |
| Lazy delivery | "Happens later" is a row with `deliver_at` timestamp, filtered on read. No background workers. | Simple, auditable, works in SQLite |
| LLM provider abstraction | `LLM_PROVIDER=stub\|ollama\|anthropic\|openrouter` with a dispatcher pattern | Same codebase runs in demo mode (no keys) or production (real LLM) |
| Tiered deployment | Three tiers: Demo, Standard, Full | Progressive adoption — each tier adds capability without breaking the previous |
| `brief.yaml` per company | Each company has a single YAML defining employees, jobs, branding, scenario | Proven content-authoring format — Ensayo generalises it as `company.yaml` |
| AnythingLLM workspace automation | `setup-chatbots.py` creates one workspace per company, uploads career page content for RAG | Automated chatbot provisioning — no manual AnythingLLM configuration |
| Six interaction surfaces | Messaging, 1-on-1, group chat, document submission, booking, assessment — composable building blocks | Domain-independent surfaces that recompose into healthcare, finance, etc. |

**What Ensayo does differently:**

| What WorkReady Did | What Ensayo Does |
|-------------------|------------------|
| One simulation per deployment, hardcoded for one institution | Multi-simulation per instance; each VPS instance can host many simulations |
| Separate repos per company (one per `subdomain.eduserver.au`) | One repo per simulation; multi-site is subpaths of one custom domain |
| Changes require editing YAML and rebuilding manually | Dashboard-driven configuration with optional YAML export |
| SQLite without migrations | Versioned migrations |
| Email-only auth (only) | Configurable: shared password, individual accounts, email-only |
| One LLM provider per deployment | Per-simulation provider configuration |

### 2.3 TechNova Systems — The Safe-Mode Pattern

**What it is:** A managed IT services company simulation for school students (Years 10–12), with deterministic keyword-matching chatbots instead of LLM-powered ones.

**The key insight:** Deterministic chatbots are essential for environments where LLM output is inappropriate (minors, assessment integrity, no internet access, restricted PII). TechNova proves that simulations can be valuable without LLM at all.

**Ensayo treats this as a first-class deployment mode** (§7), not a degraded fallback. School-audience simulations have different defaults: no LLM chatbots, no individual accounts, no inbox/messaging surface, no per-student logging. The audience setting is a bundle of defaults applied at simulation-creation time, with override banners for any deviation.

### 2.4 Company Sites — The Repo Pattern

All six WorkReady company sites follow an identical layout:

```
{company}/
├── brief.yaml          # Authoritative content definition
├── jobs.json           # Generated job listings
├── content/
│   ├── employees/      # {slug}.md + {slug}-prompt.txt per employee
│   └── docs/           # Support and policy documents
├── site/
│   ├── build.py        # Jinja2 + YAML → static HTML
│   ├── templates/
│   ├── styles/
│   └── scripts/
└── dist/               # Built output (deployed to GitHub Pages)
```

This pattern is already de-facto standardised. Ensayo formalises it and unifies the per-company `build.py` into a single generator that operates on either a single `company.yaml` or a multi-site `simulation.yaml`.

### 2.5 What Ensayo Does That No Reference Does

| New capability | Why |
|----------------|-----|
| Multi-simulation per instance | Reduce institutional VPS-approval burden — one approval covers all simulations a department runs |
| Lay-person wizard producing YAML | Non-technical UCs can scaffold without seeing YAML |
| Configurable workflow engine | Generalise WorkReady's hardcoded internship lifecycle to other domains |
| Audience-aware defaults | Make school-safe deployment a one-click setting |
| Open self-host with no SaaS | No subscription, no vendor risk, no data egress |

---

## 3. Architecture Overview

### 3.1 Component Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           VPS (Ensayo Instance)                           │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                  Ensayo Services (FastAPI monolith)                 │  │
│  │                                                                      │  │
│  │  • Instance admin endpoints                                         │  │
│  │  • UC dashboard (HTML/JS at /admin/)                                │  │
│  │  • Generator engine (imported as Python library)                    │  │
│  │  • Booking, messaging, conversation, group chat, task surfaces      │  │
│  │  • Workflow engine                                                  │  │
│  │  • Student auth (shared / individual / email-only)                  │  │
│  │  • Visibility & phased release enforcement                          │  │
│  │  • LLM proxy (keys stay server-side)                                │  │
│  │  • AnythingLLM workspace provisioner                                │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│         │                                              │                   │
│         │ reads + writes                               │ reads + writes    │
│         ▼                                              ▼                   │
│  ┌────────────────────────────┐               ┌────────────────────────┐ │
│  │  Git Working Clones        │               │  SQLite DB             │ │
│  │  (one per simulation)      │               │                        │ │
│  │                            │               │  • Lecturer/UC accounts│ │
│  │  /var/ensayo/sims/acme/    │               │  • Simulation metadata │ │
│  │    ├─ company.yaml         │               │    (cache, rebuildable)│ │
│  │    ├─ content/             │               │  • Runtime state:      │ │
│  │    └─ dist/                │               │    bookings, students, │ │
│  │                            │               │    sessions, messages, │ │
│  │  /var/ensayo/sims/medical/ │               │    conversations,      │ │
│  │    └─ ...                  │               │    tasks, group chats  │ │
│  └────────┬───────────────────┘               └────────────────────────┘ │
│           │                                                                │
│           │ git commit + push (YAML + dist/)                              │
│           ▼                                                                │
└───────────┼────────────────────────────────────────────────────────────────┘
            │
   ┌────────▼─────────┐                          ┌──────────────────────┐
   │  GitHub          │                          │  AnythingLLM         │
   │  (one repo per   │                          │  (optional, external │
   │   simulation,    │                          │   or same VPS)       │
   │   gh-pages)      │                          │                      │
   └────────┬─────────┘                          └──────────────────────┘
            │ GitHub Pages serves dist/
            ▼
   ┌──────────────────────────┐
   │ Students access static   │
   │ site at custom domain    │
   │ (subpath multi-site)     │
   └────────┬─────────────────┘
            │ browser JS calls API on VPS for dynamic features
            ▼
        (back to Ensayo Services on VPS)
```

### 3.2 Component Descriptions

#### Ensayo Services (FastAPI monolith on VPS)

A single FastAPI application serving every dynamic feature. Routers are organised by surface:

- `/admin/` — instance admin and UC dashboard (HTML/JS app + JSON API)
- `/api/v1/auth/` — student authentication for all three modes
- `/api/v1/bookings/` — appointment scheduling
- `/api/v1/chat/` — LLM proxy for chatbot conversations
- `/api/v1/messages/` — in-app messaging (lazy delivery)
- `/api/v1/conversations/` — 1-on-1 LLM conversations
- `/api/v1/group-chats/` — multi-participant LLM conversations
- `/api/v1/tasks/` — document submission and review
- `/api/v1/workflow/` — stage advancement
- `/api/v1/content/` — visibility-enforced content fetch (for sensitive content not pushed to public dist/)

Technology: **FastAPI**, **SQLite** (WAL mode for concurrent reads), **Pydantic** validation, **httpx** for outbound LLM calls.

#### Generator Engine (Python library, also a CLI)

A Python module (`ensayo.generator`) that reads `company.yaml` or `simulation.yaml` and produces:

- A complete static HTML/CSS/JS site in a `dist/` directory
- **Employee prompt files at `<simulation>/content/employees/{slug}-prompt.txt`** — these are the canonical persona prompts (pattern adopted from workready-api). The API reads them at runtime from disk via the `SITES_DIR` env var pointing at the working clones path. Editing a persona = editing a `.txt` file in the repo (which the dashboard pushes), not a DB row.
- AnythingLLM workspace specifications (workspace names, system prompts, RAG document lists)
- A `jobs.json` file for multi-site job board integration
- Document stubs from templates

The generator is imported by the dashboard for in-process generation; it is also installed as the `ensayo` CLI for power users and CI/CD workflows.

The generator orchestrates **Astro theme packages** to produce the static HTML site. See §13 for the theme architecture: each theme is a full Astro project with its own templates, components, and scoped CSS, derived from a corresponding hand-built WorkReady site.

Technology: **Python 3.12+** for orchestration, content management, LLM calls, AnythingLLM provisioning (Click, PyYAML, httpx). **Astro + Node 20+** for theme rendering only — runs on the VPS at build time, never required at deploy time. The build pipeline invokes `npm ci && npm run build` against the chosen theme package. Output is pure static HTML/CSS/JS that GitHub Pages serves without any runtime Node dependency.

#### Git Working Clones (on VPS disk)

The dashboard maintains one working clone per simulation under a standard path (e.g. `/var/ensayo/sims/{simulation-slug}/`). When a UC edits content, the dashboard:

1. Acquires a per-simulation lock
2. Pulls the latest from origin (defensive — in case someone edited via GitHub web UI)
3. Updates YAML files in the working clone
4. Re-runs the generator to update affected dist/ pages
5. Commits both YAML and dist/ changes
6. Pushes to GitHub
7. Releases the lock

This means GitHub Pages always serves up-to-date dist/ without requiring CI. The VPS holds the git credentials (PAT or SSH key); UCs never touch git directly.

#### SQLite Database (on VPS)

One database file per Ensayo instance. Stores:
- Instance admin account
- UC accounts
- Simulation metadata cache (rebuildable from YAML)
- All runtime state — bookings, students, sessions, messages, conversations, tasks, group chats, visibility-rule evaluations

Never committed to git. Backed up via standard VPS snapshots or `sqlite3 .backup`.

#### Static Sites on GitHub Pages

The student-facing surface of every simulation. Pure HTML/CSS/JS. Dynamic interactions are JS calls to the VPS API. CORS is configured per-simulation to allow the simulation's custom domain to call the API origin.

#### AnythingLLM (optional)

External service providing per-employee chatbot workspaces with RAG. The Ensayo Services component provisions workspaces via AnythingLLM's API. AnythingLLM may be deployed on the same VPS (via Docker compose) or externally.

When AnythingLLM is unavailable, chatbots fall back to either keyword mode or the LLM proxy (system prompt without RAG).

### 3.3 Storage Architecture

Three layers, with explicit canonical-vs-cache directionality:

| Layer | Where | Format | Canonical for | Direction of writes |
|-------|-------|--------|--------------|--------------------|
| Git repo | GitHub + VPS working clone | YAML, Markdown, built HTML | Simulation content (companies, employees, documents, prompts, themes) | Dashboard writes YAML in working clone, regenerates dist/, commits, pushes |
| SQLite | VPS only | Relational tables | Runtime state AND a rebuildable cache of simulation metadata | Dashboard writes runtime data; cache is updated when YAML changes |
| AnythingLLM | External service | Proprietary | Chatbot workspace index | Provisioned by Ensayo on simulation creation; updated when employee prompts change |

**Why YAML is canonical for content:**
- Version control — UCs get rollback for free via git history
- Diffability — UCs and admins can review changes
- Open data — simulations are portable; another instance can clone the repo and run
- Resilience — losing the SQLite DB doesn't lose any simulation content

**Why SQLite is canonical for runtime:**
- Per-student state is volatile, frequent, and PII-sensitive
- Should not be in a public git repo
- Can be independently backed up
- Allows cache rebuild from YAML if metadata gets out of sync

### 3.4 Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| **Single FastAPI monolith on a VPS** | Concurrent users in tens, not thousands. One process, one DB, one deployment unit. Routers provide internal modularity. |
| **Generator runs on the VPS, not in CI** | Avoids GitHub Actions complexity, secret management, and Action minute quotas. The dashboard's edit flow is synchronous: edit → regenerate → commit → push. Total time: a few seconds for typical edits. |
| **Astro themes for site rendering** | Each WorkReady company site has its own distinctive visual language; one parameterised template cannot reproduce that. Themes are Astro packages with their own templates, components, and scoped CSS. Node is build-time only on the VPS; deployed sites are pure static HTML on GitHub Pages. |
| **One repo per simulation** | Clean ownership boundary, simpler dashboard logic, predictable URL structure. Multi-site sims live in subpaths of one custom domain (`acme-sim.eduserver.au/portal/`, `/nexuspoint/`). |
| **YAML + Markdown for content, JSON for machine output, SQLite for runtime** | YAML is human-edited; JSON files like `employees.json` and `jobs.json` are generator output; SQLite is for state that doesn't belong in git. |
| **Lazy delivery for time-based events** | Proven in WorkReady. No background workers, no job queues. Rows with `deliver_at` timestamps, filtered on read. |
| **Open self-host with one Docker compose** | Lowers the barrier for individual educators while still serving institutions. The same image runs locally, on a $5 VPS, or on institutional infrastructure. |
| **Idempotent migrations on startup** | Pattern from workready-api: `_migrate()` runs on every API start and adds columns `IF NOT EXISTS`. Safe to re-run; no separate migration tool needed. New migrations follow the same add-column-with-IF-NOT-EXISTS pattern. Schema evolution does not block deployment. |

### 3.5 Assumptions

1. **Concurrent students are in the tens, not thousands.** A typical simulation serves one or two classes (20–80 students). This justifies SQLite and single-process deployment.
2. **Simulations have at most a handful of UCs each.** Multi-UC editing is sequential (per-simulation lock); concurrent edits are rare.
3. **GitHub Pages is the primary static hosting target.** Other static hosts work, but GitHub Pages is the default — free, stable, well-known.
4. **The instance admin and UC are trusted users.** They get broad powers (content management, git push, student data access). The threat model is misconfiguration, not adversarial admins.
5. **Student data privacy is a deployment concern.** The platform provides mechanisms (audience modes, optional account modes, data export/delete). Compliance with institutional policies is the deployer's responsibility.
6. **AnythingLLM is optional.** Keyword chatbots and direct LLM proxy work without it.

### 3.6 Observability and Logging

Ensayo emits structured JSON logs from the API. Logs go to stderr and a rotated file under `/var/ensayo/logs/`. The platform itself does **not** include a log viewer, dashboard, or analytics UI — that's deliberately deferred so the platform stays focused.

**What's logged:**

- **API requests** — method, path, UC/student id (or null in shared-password mode), response code, latency
- **Generation events** — job_id, items generated, tokens consumed (input + output), provider, success/failure, partial-failure recovery
- **Audit events** — UC X edited employee Y at timestamp Z; UC X published simulation S; admin Q created UC R
- **Errors** — full stack traces with correlation IDs students can quote when reporting issues
- **Notification dispatch** — channel, event type, success/failure
- **Theme override warnings** (§13.7) — when a UC selects a configuration the chosen theme does not advertise support for

**What is NOT logged when `audience: minors`:**

- Per-student request paths (aggregate counts only)
- Conversation content
- Document submission content
- Free-text inputs of any kind

This is consistent with the §7 minors-safe bundle — minimal logging, aggregate only.

**Future work:** a separate observability tool consumes the JSON log stream — log aggregation, dashboards, alerting, log-shipping to ELK/Loki/Grafana, etc. Out of scope for the platform; pluggable for institutions that want it.

### 3.7 Notification Adapter Pattern

Pattern adopted from `workready-api/notifications.py`. All student communications flow through a single dispatcher (`notify()`), not directly to delivery channels:

```
Code that needs to communicate with a student:
  notify(student_id, event_type='task_reviewed', payload={...})
                              │
                              ▼
                ┌─────────────────────────┐
                │  notify() dispatcher    │
                │  + _EVENT_ROUTES table  │
                └────────────┬────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
  ┌───────────┐      ┌──────────────┐      ┌───────────────┐
  │ in_app    │      │ email        │      │ telegram /    │
  │ inbox     │      │ (SMTP)       │      │ teams (later) │
  │ (default) │      │ (optional)   │      │ (optional)    │
  └───────────┘      └──────────────┘      └───────────────┘
```

**Why this matters:**
- Adding a new delivery channel is a `register_channel(name, handler)` call plus an entry in `_EVENT_ROUTES`. Call sites do not change.
- Per-student notification preferences plug in here (a student opts out of email but keeps in-app).
- The minors-safe audience bundle disables non-in-app channels by default.
- Surface-specific routing rules live in one table — e.g. lunchroom messages go to the **work** inbox, not personal.

**MVP:** in-app inbox only (Phase 3). Email, Telegram, Teams are later phases when institutional integration matters.

---

## 4. Data Model

### 4.1 Entity-Relationship Overview

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│   Instance   │       │   Simulation     │       │   Workflow   │
│   Admin      │◄──────│   (per repo)     │──────►│   Config     │
└──────────────┘       └────────┬─────────┘       └──────┬───────┘
                                │                         │
                    ┌───────────┼───────────┐            │
                    ▼           ▼           ▼            ▼
             ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
             │ UC       │ │ Company  │ │ Student  │ │ Audience     │
             │ Account  │ │ Site (×N)│ │ Access   │ │ Mode         │
             └──────────┘ └────┬─────┘ └────┬─────┘ └──────────────┘
                               │            │
                    ┌──────────┼────────────┼───────────────┐
                    ▼          ▼            ▼               ▼
             ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
             │ Department│ │ Employee │ │ Document │ │ Booking      │
             │           │ │          │ │          │ │              │
             └───────────┘ └────┬─────┘ └──────────┘ └──────────────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
             ┌────────────┐ ┌────────┐ ┌───────────────┐
             │ Chatbot    │ │ Task   │ │ Visibility    │
             │ Workspace  │ │ Templt │ │ Rule          │
             └────────────┘ └────────┘ └───────────────┘
```

### 4.2 Entity Definitions

#### Simulation

The top-level container. One Ensayo instance hosts many simulations. Each simulation is an independent teaching scenario with its own repo.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `name` | string | Human-readable name (e.g. "CloudCore Networks — ISYS6018 Sem1 2026") |
| `slug` | string | URL-safe identifier; matches the simulation's directory name on disk |
| `type` | enum | `single_company` or `multi_site` |
| `audience` | enum | `adults` or `minors` (see §7) |
| `owner_uc_id` | FK → UC | UC who created this simulation |
| `repo_url` | string | Git remote URL (GitHub) |
| `working_clone_path` | string | Local path on VPS (e.g. `/var/ensayo/sims/cloudcore-isys6018-2026/`) |
| `site_url` | string | Public URL for the deployed simulation (e.g. `https://cloudcore.eduserver.au/`) |
| `config_cache` | JSON | Cached `company.yaml` or `simulation.yaml` content (rebuildable from YAML) |
| `status` | enum | `draft`, `active`, `archived` |
| `has_unpublished_changes` | boolean | True when the working clone YAML differs from the last-published commit (see §10.1 Save vs Publish) |
| `auto_publish` | boolean | When true, every Save triggers an immediate Publish — useful for solo authoring or pre-cohort iteration |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

#### UC Account (Lecturer / Unit Coordinator)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `email` | string | Unique, used for login |
| `password_hash` | string | bcrypt |
| `display_name` | string | |
| `role` | enum | `instance_admin`, `uc` |
| `created_at` | timestamp | |
| `last_login_at` | timestamp | |

#### Simulation Co-Coordinator

Maps additional UCs to simulations they help run.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `simulation_id` | FK → Simulation | |
| `uc_id` | FK → UC | |
| `unit_code` | string | Teaching unit this UC manages within the simulation |
| `permissions` | JSON | `{can_edit_shared_content: bool, can_manage_students: bool, ...}` |
| `created_at` | timestamp | |

#### Company

A fictional organisation within a simulation. In `single_company` simulations there is exactly one. In `multi_site` simulations there are many.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `simulation_id` | FK → Simulation | |
| `name` | string | "CloudCore Networks" |
| `slug` | string | "cloudcore-networks" |
| `tagline` | string | Optional |
| `industry` | string | References industry templates |
| `location` | string | "Perth, Western Australia" |
| `founded` | integer | Year |
| `employee_count` | integer | Stated headcount |
| `revenue` | string | "$45M annually" |
| `description` | text | Markdown |
| `theme` | string | Theme directory name |
| `branding` | JSON | Color overrides, logo path, font preferences |
| `subpath` | string | URL subpath in multi-site (e.g. `nexuspoint`); empty for single-company |
| `chatbot_mode` | enum | `llm`, `keyword`, `hybrid` |
| `booking_enabled` | boolean | Whether the booking system is active for this company |
| `business_hours` | JSON | `{start: 9, end: 17, days: [1,2,3,4,5], timezone: "Australia/Perth"}` |
| `culture` | JSON | Tone, values, communication norms |
| `scenario` | JSON | Scenario narrative, tensions, key events |

#### Department, Employee, Document, Visibility Rule, Student Access, Application, Booking, Task Template, Message, Conversation Session, Task Instance, Task Submission, Group Chat Session, Group Chat Post

These are unchanged from v1 in their schema. Refer to v1 §4.2 for full field definitions. Notable refinements in v2:

**Student Access — identity is internal, not email-derived:**

- `id` (UUID) is the canonical primary key — every other table foreign-keys to this, never to email
- `email` is a mutable identifier — students can update their email without losing identity or history
- `deleted_at` (timestamp, nullable) supports soft delete (§6.6) — preserves DB referential integrity while honouring deletion requests; conversation transcripts and task submissions are anonymised but retained for cohort analytics
- `status` enum extended with `deleted` value
- No reactivation mechanism: a deleted student returning is a new account with a new `id`. Their previous email becomes available for reuse after a configurable retention period (default 30 days).

**Other notable points:**

- **Visibility Rule** (`visibility_rules` table) is the per-unit customisation mechanism described in §13.3. Each rule is scoped to a `unit_code`, allowing co-coordinators to hide content for their unit only.
- **Conversation Session** generalises WorkReady's `interview_sessions` table — the `kind` field distinguishes hiring interview, coaching, exit interview, clinical consultation, investor pitch, etc.
- **Group Chat Session** generalises WorkReady's `lunchroom_sessions` — same lazy-delivery beat-arc pattern, parameterised by `occasion`.
- **Message** implements the dual-inbox lazy-delivery pattern proven in WorkReady.

### 4.3 Storage Locations and Source of Truth

Data lives in three places with explicit canonical-vs-cache semantics:

| What | Where | Format | Canonical? |
|------|-------|--------|-----------|
| Simulation content (companies, scenario, branding, theme choice, document metadata) | `company.yaml` / `simulation.yaml` in repo | YAML | **Yes — git is canonical** |
| Document bodies | `content/docs/*.md` in repo | Markdown | **Yes — git is canonical** |
| Persona prompts | `content/employees/{slug}-prompt.txt` in repo | Plain text | **Yes — git is canonical**. API reads at runtime via `SITES_DIR` env var pointing at the working clones path. |
| Generated site (`dist/`) | Same repo, `dist/` directory | HTML/CSS/JS | Derivable from YAML + Markdown + prompts via the generator |
| Simulation metadata cache | SQLite `companies`, `employees`, `documents` tables | Relational | Cache only — rebuildable from YAML |
| Runtime state (bookings, students, sessions, messages, conversations, tasks, group chats) | SQLite | Relational | **Yes — DB is canonical** |
| UC and admin accounts | SQLite | Relational | **Yes — DB is canonical** |
| Chatbot workspaces | AnythingLLM internal storage | Proprietary | AnythingLLM canonical (provisioned from YAML on creation) |

**Direction of writes:**

```
UC dashboard edit (e.g. "change Marcus's backstory"):
  1. Acquire per-simulation lock
  2. Pull from origin (defensive)
  3. Write YAML to working clone
  4. Run generator → update affected dist/ pages
  5. Commit YAML + dist/
  6. Push to origin
  7. Update DB cache for fast reads
  8. (If chatbot prompt changed) Update AnythingLLM workspace
  9. Release lock

Student runtime action (e.g. "book an appointment"):
  1. POST to /api/v1/bookings/
  2. Insert row in SQLite
  3. (No git interaction)
```

**Rebuild scenarios:**

- Lost SQLite DB but git intact: `ensayo ingest <repo>` rebuilds the metadata cache from YAML. Runtime state (bookings, conversations) is lost — restore from backup separately.
- Lost VPS but GitHub intact: clone the repo to a new VPS, `ensayo ingest`, restore SQLite from backup.
- Lost git but DB intact: dashboard can serialise DB cache back to YAML and re-create the repo (last-resort recovery).

---

## 5. Deployment Model

### 5.1 The Single Deployment Model

There is one supported deployment shape: **VPS-hosted services + GitHub Pages-served static sites.**

```
                ┌─────────────────────┐
                │    LLM Provider     │
                │  (Ollama / OpenAI / │
                │   Anthropic / etc.) │
                └──────────┬──────────┘
                           │
                           │
┌────────────────────────────────────────────────┐
│                                                │
│                   VPS                          │
│                                                │
│   ┌────────────────────────────────────┐      │
│   │  Ensayo Services (FastAPI)         │      │
│   │  + Generator                       │      │
│   │  + UC Dashboard                    │      │
│   │  + SQLite DB                       │      │
│   │  + Git working clones              │      │
│   └────────────────────────────────────┘      │
│   ┌────────────────────────────────────┐      │
│   │  AnythingLLM (optional, same       │      │
│   │  Docker compose stack)             │      │
│   └────────────────────────────────────┘      │
│                                                │
└────────────────────┬───────────────────────────┘
                     │
                     │ git push
                     ▼
              ┌──────────────┐
              │   GitHub     │   ← gh-pages branch
              │   (one repo  │     served as static site
              │   per sim)   │
              └──────┬───────┘
                     │
                     │ HTTPS (custom domain)
                     ▼
              ┌──────────────┐
              │   Students'  │
              │   Browsers   │
              └──────┬───────┘
                     │
                     │ JS calls to /api/v1/* on VPS
                     ▼
                  (back to VPS)
```

### 5.2 What Lives Where

| Capability | Location |
|-----------|----------|
| Public marketing pages (homepage, about, services) | Static — GitHub Pages |
| Document library (policies, procedures, reports) | Static — GitHub Pages |
| Employee profile pages | Static — GitHub Pages |
| Keyword chatbots | Static — GitHub Pages (client-side JS + JSON) |
| LLM chatbots (via AnythingLLM embed) | Static page + AnythingLLM service |
| LLM chatbots (via API proxy) | Static page calls VPS API |
| Booking system | VPS API; static page modal calls it |
| Authentication (all three modes) | VPS API; static page form calls it |
| Visibility / phased release | VPS-enforced; static page requests gated content from API |
| Inbox / messaging | VPS API; portal page renders from API |
| Conversation surfaces (interview, coaching, etc.) | VPS API |
| Task submission and review | VPS API |
| Group chat | VPS API |
| Workflow engine | VPS API |
| UC dashboard | VPS, served at `/admin/` on the VPS's own domain |

### 5.3 Deployment Tiers

Each tier builds on the previous. The simulation works at every tier — each step adds capability without breaking the previous.

| Tier | What It Adds | Requires | Audience | Pre-built image? |
|------|-------------|----------|----------|------------------|
| **1 — Demo** | Zero config: stub LLM, keyword chatbots, path-based Caddy routing on `:80`, shared password auth | Docker only | Evaluation, tutorials, classroom demos | ✅ Yes (GHCR) |
| **2 — Standard** | Real LLM provider, real chatbot conversations, booking, full dashboard, custom domain | Docker + LLM key + custom domain | Pilot cohorts, single-class teaching | ✅ Yes (same image, add API key) |
| **3 — Full** | AnythingLLM with RAG, individual student accounts, full analytics, multi-site simulations | Docker + LLM key + custom domain + AnythingLLM | Production teaching at institutional scale | ⚠ Local build (AnythingLLM embed UUIDs are baked into generated dist/ at simulation creation time) |

### 5.4 Zero-Config First Run (Tier 1)

The pre-built image at `ghcr.io/your-org/ensayo:latest` is published on every push to main. First-time evaluation needs nothing but Docker:

```bash
git clone https://github.com/your-org/ensayo.git
cd ensayo
docker compose up -d
# → Open http://localhost
```

**What works immediately:**
- Caddy on `:80` with **path-based routing fallback** — every simulation lives at `http://localhost/sims/{slug}/`, no DNS needed
- Stub LLM (`LLM_PROVIDER=stub`) — interview, assessment, content-generation surfaces return canned responses
- Keyword chatbot (~100 lines client-side JS, no external dependencies) on every employee page
- Shared-password auth
- Full dashboard at `http://localhost/admin/`
- A demo simulation pre-loaded so the experience is non-empty
- **All theme packages bundled and pre-installed** in the image — `node_modules` for each theme is vendored so first-run never hits npm. The user can rebuild any included theme without internet beyond the initial `docker pull`.

This is a deployment guarantee: **Ensayo always launches with a working simulation, even with no API keys, no DNS, no AnythingLLM, no internet after the initial pull.** Demoing the platform to an institutional decision-maker takes one command.

**Image contents:** Python 3.12, Node 20, Caddy, Ensayo Python package, all bundled themes (with vendored `node_modules`), demo simulation YAML, SQLite. No external network calls required for first run.

### 5.5 Configured Deployment (Tier 2 / Tier 3)

For real teaching, add configuration:

```bash
# 1. Install Docker on a VPS ($5–20/month)
# 2. Clone Ensayo
git clone https://github.com/your-org/ensayo.git
cd ensayo

# 3. Configure (two files, separated by purpose)
cp instance.env.example instance.env   # domain, admin email, base URL
cp .env.example .env                   # secrets: LLM keys, GitHub token, AnythingLLM key

# 4. Start
docker compose up -d

# 5. Create instance admin account
docker compose exec ensayo ensayo admin create --email you@example.edu

# 6. Log in to dashboard at https://ensayo.eduserver.au/admin/
# 7. Create your first UC account, then your first simulation
```

The docker compose stack includes Ensayo services, Caddy (TLS via Let's Encrypt), and optionally AnythingLLM and Ollama.

### 5.6 Configuration File Split

Two env files, separated by intent (pattern adopted from workready-deploy):

| File | Purpose | Reviewable | Examples |
|------|---------|-----------|----------|
| `instance.env` | What runs where | Yes — safe to share | `ENSAYO_DOMAIN`, `ADMIN_EMAIL`, `BASE_URL`, `WORKING_CLONES_DIR` |
| `.env` | Credentials | No — never commit | `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `ANYTHINGLLM_API_KEY`, `JWT_SECRET` |

This separation matters for institutional procurement: domain configuration can go through review while secrets stay in a separately-protected vault.

### 5.7 Caddy and CORS

Caddy is responsible for:
- TLS termination (Let's Encrypt) when domains are configured
- Path-based fallback routing (`/sims/{slug}/`) when no domains are configured — workready's `{$DOMAIN_X:fallback.localhost}` pattern
- CORS headers — the API itself does not need per-deployment origin allow-lists; Caddy injects headers based on the configured custom domain(s) or wildcard for Tier 1

This keeps the API generic across deployments. Switching from Tier 1 (no DNS) to Tier 2 (custom domain) is a Caddy config change, not an application change.

### 5.8 The Single Install Script

Pattern adopted from `workready-deploy/install.sh`: one script is the source of truth for both bare-metal and Docker deployments.

```
install.sh
  ↓ runs identically when:
  ├── piped from curl on a fresh VPS
  └── RUN inside the Dockerfile during docker build
```

The Dockerfile copies `install.sh` and runs it. Bare-metal users `curl | bash` the same script. The output is a working `/opt/ensayo/` directory with Caddy, uv, the Python service, and a starter SQLite DB.

**Idempotency:**
- `git pull --ff-only` if the Ensayo repo is already cloned, else clone fresh
- `SKIP_DEPS=1` to skip system dependency installation
- `SKIP_CLONE=1` if the repo is already in place
- Re-running the script is safe — it advances state but does not destroy data

Bare-metal upgrade: re-run `install.sh`. Docker upgrade: `docker compose pull && docker compose up -d`.

### 5.9 Future: Per-Site Custom Domains

The default is subpath multi-site: `https://acme-sim.eduserver.au/portal/`, `/nexuspoint/`, `/ironvale/`, etc. This sacrifices some realism — WorkReady originally had `nexuspoint.eduserver.au`, `ironvale.eduserver.au` — but simplifies ownership, deployment, and dashboard logic.

**Per-site domains** are deferred to a future phase. Implementing them requires:
- Multiple repos per simulation (one per company site)
- DNS configuration for each domain (more procurement burden)
- Dashboard logic for coordinated multi-repo edits
- Cost increase if domains are purchased per site

For deployers who genuinely need per-site realism, the workaround in MVP is to deploy each company as a separate single-company simulation and link them manually. Multi-site mode is available but uses subpaths.

---

## 6. Authentication and Access Control

### 6.1 Three Tiers of Identity

**Tier 1: Instance Admin** (the deployer of the VPS)
- Full root access to the Ensayo instance
- Creates UC accounts (and optionally invites them via email)
- Configures global LLM providers and AnythingLLM connection
- Manages instance-wide settings (theme defaults, base library version, AnythingLLM URL)
- Can access any simulation on the instance for debugging or recovery
- Typically the same person as the technical owner of the VPS

**Tier 2: Unit Coordinator (UC) / Lecturer**
- Created by the instance admin (or self-registered if the admin enables open registration)
- Creates and owns simulations (becomes the simulation's `owner_uc`)
- Edits content, manages students, monitors engagement for simulations they own
- Can be added as a co-coordinator to other UCs' simulations
- Cannot access simulations they neither own nor co-coordinate

**Tier 3: Student**
- Authenticated per simulation, not per instance
- Three modes: shared password, individual account, email-only (see §6.3)
- Has no dashboard access; interacts only with the simulation site

### 6.2 Simulation Ownership and Sharing

Each simulation has exactly one **owner UC** (the creator). The owner can invite other UCs as **co-coordinators**, each scoped to a specific `unit_code`.

**Owner permissions:**
- Edit any content in the simulation (employees, documents, scenario, theme)
- Add/remove co-coordinators
- Configure audience mode and authentication
- Delete the simulation
- Transfer ownership

**Co-coordinator permissions (default):**
- View all content
- Manage students for their unit
- View analytics for their unit
- Add **per-unit visibility rules** to hide content for their unit only
- Add unit-scoped supplementary content (e.g. extra documents visible only for their unit)

**Co-coordinator restrictions:**
- Cannot modify shared canonical content (employee backstories, base documents)
- Cannot delete the simulation
- Cannot modify the audience mode or auth mode

For modifications beyond hiding, a co-coordinator either requests the change from the owner or **clones the simulation** into their own repo. Cloning is a first-class dashboard action: it creates a new simulation owned by the cloner, with content copied at clone-time. The two simulations then diverge independently.

### 6.3 Student Authentication Modes

#### Mode 1: Shared Password

A single password per unit/scenario. Students enter the password to access the simulation. No individual identity.

| Aspect | Detail |
|--------|--------|
| Identity | None beyond the password |
| Tracking | Not possible (everyone shares one password) |
| Analytics | Aggregate only (page views, booking counts) |
| Privacy | Minimal — no student data collected |
| Server enforcement | The VPS API verifies the password before serving gated endpoints |

**When to use:** Low-stakes teaching, school-audience simulations (forced default for `audience: minors`), workshops, demonstrations.

#### Mode 2: Individual Accounts

Each student creates an account with email and password. The UC can pre-register students via CSV upload (whitelist).

| Aspect | Detail |
|--------|--------|
| Identity | Email + name per student |
| Tracking | Full — per-student page views, bookings, chat history, task submissions |
| Analytics | Per-student engagement metrics, journey reports |
| Privacy | Requires institutional privacy clearance. PII stored in SQLite. |

**Optional features:**
- **Whitelist (CSV upload):** Only whitelisted emails can register
- **Password reset via email** (requires SMTP)
- **Student profile/settings** (display name, timezone, notification preferences)

**When to use:** Production teaching, multi-stage simulations requiring per-student state (WorkReady-style internships), assessment contexts.

#### Mode 3: Email-Only

Students sign in with just an email address. No password. The email is the identity token.

| Aspect | Detail |
|--------|--------|
| Identity | Email only |
| Tracking | Per-student activity tied to email |
| Analytics | Per-student metrics |
| Privacy | Lower than individual accounts (no password stored), but email is still PII |

**When to use:** Mid-stakes simulations where reduced friction matters and impersonation risk is low. Proven in WorkReady.

### 6.4 Authentication Behaviour

All three modes are **server-verified by the VPS API**. There is no client-side-only authentication; the static site never trusts JS state for access decisions. When a student attempts to access gated content, the static page calls `/api/v1/auth/verify`, and the API enforces the rule.

This is a change from v1's "static mode allows client-side gates" — that path is removed because there is no purely-static deployment.

### 6.5 Access Control Rules

Beyond authentication, Ensayo supports content-level access control:

1. **Visibility rules** (§4.2) — time-based or condition-based show/hide of documents, chatbot access, pages. Server-enforced.
2. **Booking-gated chatbots** — students must book and attend an appointment before a chatbot becomes accessible (CloudCore pattern).
3. **Progress-gated content** — in multi-stage simulations, completing one stage unlocks the next (WorkReady's lazy-delivery pattern).
4. **Per-unit scoping** — visibility rules and content additions can be scoped to a `unit_code`, supporting multi-UC simulations.

### 6.6 Audit and Logging

By default the API logs:
- Authentication attempts (success/fail) per simulation
- Booking creation, cancellation, no-show
- Content modifications (which UC, which content, when) — for git push events this is also visible in commit history
- Student data exports

`audience: minors` reduces logging to aggregate counts only (see §7.2).

### 6.7 Student Data Lifecycle and Soft Delete

Ensayo uses **soft delete** for student data, not hard delete. This preserves database referential integrity (foreign keys from sessions, bookings, tasks, group chats remain valid) while honouring deletion requests for privacy compliance.

**On delete:**

1. `student_access.deleted_at` is set to the current timestamp; `status` is set to `deleted`
2. PII fields (`email`, `name`) are nulled on the `student_access` row
3. **Conversation transcripts** in `conversation_sessions.transcript` are anonymised — the student's messages are replaced with `[redacted]` while AI-side messages remain (preserving simulation analytics value)
4. **Task submission bodies** are anonymised — replaced with `[redacted]` while the assessment scores remain
5. **Messages** in the student's inbox have their bodies redacted; metadata (timestamps, sender, kind) remains
6. **AnythingLLM workspace history**: AnythingLLM stores its own chat history per workspace; on student delete, the platform calls AnythingLLM's API to remove that student's chat threads from each workspace they used

**No reactivation:**

A deleted student returning to a simulation creates a new `student_access` row with a new `id`. They do not reclaim their previous progress. Their previous email becomes available for reuse after a configurable retention period (`STUDENT_EMAIL_RETENTION_DAYS`, default 30) so the same person can re-register without ambiguity, but they are a new identity from the platform's perspective.

**Why no reactivation:**

Conflating "reactivation" with "new account" creates audit ambiguity (was this conversation transcript made by the same person? what does deletion mean if the data comes back?). Cleaner to say: deletion is permanent in identity terms; the previous identity's anonymised analytics remain in the cohort record.

**Hard delete (rare):**

For escalated requests (a regulator orders complete erasure), an admin-only `ensayo admin purge-student --id <uuid>` command does a true hard delete: removes the row, removes all FK-cascading rows, removes AnythingLLM history. Use sparingly — irreversible and may leave audit log gaps.

---

## 7. Safe Mode and Audience Configuration

### 7.1 The Audience Setting

When creating a simulation, the UC selects an audience:

| Audience | LLM | PII | Free Input | Default Configuration |
|----------|-----|-----|------------|----------------------|
| `adults` | Allowed | Allowed | Allowed | Default — full feature set |
| `minors` | Restricted | Restricted | Reviewed | Safe Mode bundle (see §7.2) |

The audience setting is a **bundle of defaults**, not a single flag. It cascades across multiple subsystems. Individual settings can be overridden, but each override displays a persistent, non-dismissible banner: *"You are modifying a minors-safe configuration. Confirm you understand the implications."*

The audience setting is set at simulation creation. Changing it later is allowed but requires explicit owner confirmation and updates to multiple downstream defaults.

### 7.2 Minors-Safe Bundle (Defaults When `audience: minors`)

| Subsystem | Default Setting |
|-----------|----------------|
| Chatbot mode | `keyword` only — LLM chatbots disabled globally for the simulation |
| Auth mode | `shared_password` — no individual accounts, no email collection |
| Messaging surface | Disabled |
| Inbox / portal | Disabled — single-company simulations only |
| Group chat surface | Disabled |
| Conversation surface (1-on-1 LLM) | Disabled |
| Task submission | Allowed but text-only — no file upload |
| Student-generated content display | Reviewed — instructor must approve before display |
| LLM-assist in dashboard | Hard-confirm dialog before each use; disabled by default |
| Logging | Aggregate only — no per-student logs |
| Analytics export | Aggregate only |
| Privacy notice | Auto-generated on the homepage and at any data-collection point |
| Multi-site mode | Disabled — minors-safe simulations are always single-company |

### 7.3 Override Banners

If the UC overrides any minors-safe default, the dashboard displays a persistent banner showing what is non-default:

```
⚠ This simulation is marked for minor audiences but has 2 non-default settings:
   • LLM chatbots are enabled (overrides keyword-only default)
   • Individual accounts are enabled (overrides shared-password default)
   [Review overrides]  [Revert to safe defaults]
```

The banner cannot be dismissed; it is only resolved by reverting overrides or formally acknowledging each one. Acknowledged overrides are logged with timestamp and UC ID.

### 7.4 Why a Bundle, Not Individual Toggles

A novice UC building their first simulation for Year 9 students should not need to know the implications of LLM toxicity, PII regulation, content moderation, or chat safety — they should have a defensible default. The bundle provides that default. The override banners ensure that anyone bypassing the bundle has explicitly chosen to do so, with a clear record.

This also creates a clean institutional review path: a school IT admin can verify a simulation is minors-safe by checking that no overrides are active.

### 7.5 Multi-Site Simulations and Minors

Multi-site simulations are not available in `minors` mode. The interaction surfaces required for multi-site (messaging, group chat, conversations, task submission with attachments) introduce moderation burden disproportionate to school-outreach use cases. School-audience simulations are single-company by design.

### 7.6 Operational Implications

When a simulation is in `minors` mode:
- No PII export endpoints are available
- No individual-student data appears in analytics
- The dashboard's "view chat history" feature is disabled (since there are no individual students)
- The base library's role archetypes are filtered to remove any with mature themes (e.g. "crisis communications director handling press scandal" becomes unavailable)
- LLM-assisted content generation in the dashboard, if enabled by override, is wrapped with content-safety prompts ("Generate appropriate content for school-age students aged 14–17")

### 7.7 Audience Mode is Not a Security Boundary

`audience: minors` reduces risk by removing risky features. It is **not** a guarantee of perfect safety. A keyword chatbot can still respond inappropriately if its keyword list is poorly authored. A document can still contain age-inappropriate material if uploaded by the UC. Audience mode shifts defaults to the safer side; it does not absolve the UC of content review responsibility.

---

## 8. LLM Provider Abstraction

### 8.1 Design

The platform uses LLMs for two purposes:

1. **Content generation** (generator engine) — assisting with employee backstories, document drafts, scenario narratives, culture definitions. Called at generation time.
2. **Chatbot conversations** (simulation runtime) — employees responding to student queries. Called at runtime via the API or AnythingLLM.

Both use the same provider abstraction.

### 8.2 Provider Interface

```python
class LLMProvider(Protocol):
    """Interface contract for all LLM providers."""

    async def chat_completion(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 800,
        temperature: float = 0.7,
        json_mode: bool = False,
    ) -> str:
        """Send a chat completion request and return the assistant's reply text."""
        ...

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Send a single-prompt generation request."""
        ...
```

### 8.3 Supported Providers

| Provider | Config Key | Auth | Notes |
|----------|-----------|------|-------|
| Stub | `stub` | None | Deterministic responses for dev/testing |
| Ollama | `ollama` | Optional bearer token | Local or remote |
| LM Studio | `lmstudio` | Optional bearer token | OpenAI-compatible API |
| OpenAI | `openai` | API key | Direct OpenAI API |
| OpenRouter | `openrouter` | API key | OpenAI-compatible, many models |
| Google Gemini | `gemini` | API key | Google's Generative AI API |
| Anthropic | `anthropic` | API key | Claude models |

### 8.4 Configuration

Provider selection via environment variable or per-simulation config:

```bash
# Global default in .env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

```yaml
# Per-simulation override in company.yaml
llm:
  provider: openrouter
  model: anthropic/claude-sonnet-4-6
  api_key_env: OPENROUTER_API_KEY
```

**Precedence:** Simulation config → environment variable → `stub`.

### 8.5 BYOK (Bring Your Own Key)

All commercial providers support BYOK — the UC provides their own API key via the dashboard or environment variable. Keys are stored in the database (encrypted at rest) and/or environment variables. Keys are never committed to YAML files or git repositories.

### 8.6 LLM Proxy

The Ensayo Services component exposes `/api/v1/chat` to proxy chatbot requests from static frontends to the configured LLM provider. This keeps API keys server-side and allows rate limiting and logging.

When AnythingLLM is configured, it bypasses the proxy and the static site uses AnythingLLM's embed widgets directly.

### 8.7 Per-Surface Stub Bypasses

Pattern adopted from workready-api. `LLM_PROVIDER=stub` does not use one generic stub — each conversation surface has its own surface-specific stub responder, because each surface needs a different *tone* of canned response.

| Surface | Stub responder | Tone |
|---------|---------------|------|
| Hiring interview | `interview._stub_reply` | Professional, probing, ~10-turn structure |
| Mid-placement coaching | `performance_review.chat_completion_for_review` | Supportive, asks reflective questions |
| Exit interview | `exit_interview.chat_completion_for_exit` | Reflective, less judgemental, surfaces feelings |
| Group conversation (lunchroom) | `lunchroom_chat._render_beat` | Casual, multi-character, beat-arc-aware |
| Document submission review | `task_reviewer.review_task_submission` (stub mode) | Structured feedback (score + strengths + gaps) |

A single `if stub: return "ok"` would make every surface feel identical and broken. Surface-aware stubs preserve the demo experience even with no LLM keys, which is what makes the §1 zero-config-first-run guarantee actually feel right rather than visibly degraded.

**Implication for new conversation surfaces:** when adding a new `kind` to `conversation_sessions`, the implementor must also add a stub responder appropriate for that kind's tone. Stub mode is a tier-1 deliverable, not an afterthought.

---

## 9. AnythingLLM Integration

### 9.1 Integration Architecture

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  Ensayo      │     │  AnythingLLM API    │     │  Simulation Site │
│  Services    │────►│  (separate service) │────►│  (static HTML)   │
│              │     │                     │     │                  │
│  Provisions: │     │  Receives:          │     │  Embeds:         │
│  • workspace │     │  • workspace create │     │  • <script> tag  │
│    name      │     │  • system prompt    │     │    with embed    │
│  • system    │     │  • RAG document     │     │    UUID          │
│    prompt    │     │    uploads          │     │                  │
│  • RAG docs  │     │                     │     │  Renders:        │
│              │     │  Returns:           │     │  • Chat widget   │
│              │     │  • workspace ID     │     │  • Conversation  │
│              │     │  • embed UUID       │     │    UI            │
└──────────────┘     └─────────────────────┘     └──────────────────┘
```

### 9.2 Workspace Lifecycle

1. **Definition:** The generator produces a workspace specification per employee from the layered prompt builder (archetype → industry → company → individual).
2. **Provisioning:** The Ensayo Services component calls AnythingLLM's API to create the workspace, set the system prompt, upload RAG documents, and obtain an embed UUID. This happens automatically when a UC creates or updates an employee in the dashboard.
3. **Embedding:** The generated employee page includes an embed script tag.
4. **Maintenance:** Dashboard edits to system prompts or RAG documents are pushed to AnythingLLM as the dashboard saves YAML changes.
5. **Decommissioning:** When a simulation is archived, workspaces are optionally deleted.

### 9.3 RAG Document Selection

Per-employee:
- All employees default to receiving the company overview and org chart
- Per-employee customisation is possible via the dashboard (e.g. CTO gets technical docs; marketing manager gets campaign briefs)

### 9.4 Fallback Chain — A Deployment Guarantee

A simulation's chatbots always work, regardless of which services are configured. The fallback chain is:

```
1. AnythingLLM available + employee.chatbot_mode in {llm, hybrid}
   → AnythingLLM embed widget (full RAG)
   ↓ if not available
2. LLM provider configured (real or stub) + chatbot_mode in {llm, hybrid}
   → /api/v1/chat proxy (system prompt only, no RAG)
   ↓ if not available
3. Always available — chatbot_mode = keyword
   → Client-side keyword matcher reading keywords.json
   → No network requests needed
```

**Implications:**
- An Ensayo deployment with no LLM keys, no AnythingLLM, and no internet still produces working chatbots (keyword mode).
- An Ensayo deployment with stub LLM and no AnythingLLM produces working interview/coaching/exit conversation surfaces (deterministic canned responses).
- An Ensayo deployment with a real LLM key but no AnythingLLM produces character-voiced chatbots without RAG grounding.
- An Ensayo deployment with everything configured produces RAG-grounded chatbots that reference uploaded company documents.

Auto-detection happens at generation time: the dashboard probes for AnythingLLM availability and the configured LLM provider, then embeds the appropriate widget into the generated dist/. The selection is per-employee (some employees can be keyword, others LLM, in the same simulation).

**Audience-mode override:** When `audience: minors`, the chain is hard-capped at level 3 — keyword mode only, regardless of what services are configured. See §7.

---

## 10. Instructor (UC) Dashboard

### 10.1 Dashboard Architecture

The dashboard is a single-page HTML/JS application served by the Ensayo Services component at `/admin/`. It owns the git working clones for every simulation on the instance and is the only writer to those clones.

**Two-state edit model: Save vs Publish**

Edits flow through two states. **Save** is local and frequent. **Publish** is deliberate and goes live. This separation lets a UC iterate on changes mid-semester without affecting students until they're ready.

**Save (low-friction, frequent):**

```
UC clicks "Save" in dashboard
  ↓
Dashboard acquires per-simulation lock
  ↓
Dashboard writes YAML in working clone on VPS
  ↓
Dashboard updates DB cache for fast subsequent reads
  ↓
Dashboard releases lock
  ↓
Dashboard sets simulation.has_unpublished_changes = true
```

What students see: **nothing changes.** GitHub Pages still serves the last-published `dist/`.

**Publish (deliberate, less frequent):**

```
UC clicks "Publish" in dashboard
  ↓
Dashboard acquires per-simulation lock
  ↓
Dashboard pulls latest from origin (defensive)
  ↓
Dashboard runs generator on the current YAML → regenerates dist/
  ↓
Dashboard commits YAML + dist/ → pushes to origin
  ↓
GitHub Pages picks up new dist/ within ~1 minute
  ↓
Dashboard sets simulation.has_unpublished_changes = false
  ↓
Dashboard releases lock
```

What students see: the new content within ~1 minute.

**Dashboard surfaces:**

- A persistent "**N unpublished changes**" indicator on every simulation that has draft state
- A **"Discard unpublished changes"** action that reverts the working clone to the last-published commit
- A **diff view** showing what would change on Publish (which YAML files, which generated pages)
- An optional per-simulation **"Auto-publish"** toggle: when on, every Save also Publishes — useful during early simulation construction when no students have access yet, or for low-stakes iteration

**Why two states:**

A UC editing a live simulation mid-semester might want to draft several changes (a new document, a clarified employee backstory, a tweaked scenario detail) before exposing them to students. Save lets them iterate without disturbing the cohort; Publish is a deliberate "students see this now" action. For solo authoring or pre-semester simulation construction, Auto-publish removes the friction.

**Why the locking is per-simulation:**

A single simulation may have multiple co-coordinators (§6.2). The lock prevents concurrent edits from corrupting the YAML. UCs see "Simulation is being edited by alex@uni.edu" rather than a merge conflict. Lock is held briefly (single Save) — not for the whole edit session.

### 10.2 Dashboard Screens

#### Screen 1: Login

- Email + password authentication for instance admin and UCs
- JWT token (24-hour expiry, stored in localStorage)
- Password reset (if SMTP configured)

#### Screen 2: Simulation List

- Cards for each simulation the UC owns or co-coordinates
- Status badges: `draft`, `active`, `archived`
- Audience badge: `adults` or `minors`
- Actions: Edit, Clone, Archive, Delete
- "Create New Simulation" button → launches the wizard (§10.4)

#### Screen 3: Simulation Configuration (the primary workflow)

For new simulations, organised as a wizard. For existing simulations, organised as tabs.

**Step 1 — Basic Info**
- Name, type (single/multi-site), domain/discipline tags
- **Audience mode** (adults / minors) — see §7
- Auth mode (shared password / individual / email-only) — defaulted by audience
- LLM provider and key (BYOK)
- Custom domain configuration

**Step 2 — Company Setup**
- Name, tagline, industry (dropdown)
- Location, founding year, employee count, revenue
- Description (Markdown editor with optional LLM-assist)
- Theme selection (preview gallery)
- Branding overrides (color pickers, logo upload)
- Organisational culture definition

**Step 3 — Scenario**
- Scenario template selection (breach, growth, digital_transformation, crisis, merger, custom)
- Scenario narrative (Markdown editor with LLM-assist)
- Key tensions / conflicts
- Scenario timeline

**Step 4 — Employees**
- Employee list (sortable, filterable by department)
- Add employee → select archetype → LLM-assist generates backstory stub → edit → save
- Edit employee — modify backstory, personality, knowledge areas, opinions, scenario perspective
- Cross-referral map (table editor)
- Chatbot mode per employee
- Availability schedule and booking tier settings
- Import from CSV or another simulation (cloning)

**Step 5 — Documents**
- Document library with categories
- "Generate from template" — LLM produces a draft based on company context, scenario, and document type
- Upload custom documents
- Visibility rules per document
- Per-employee RAG document assignment

**Step 6 — Tasks** (multi-site only)
- Task template management
- Task assignment rules
- Difficulty and discipline tags

**Step 7 — Booking & Availability**
- Enable/disable booking
- Company business hours
- Employee availability overrides
- Booking tier defaults
- Random rescheduling probability

**Step 8 — Workflow** (multi-site only)
- Pick a workflow template (internship, medical_network, financial_markets, custom)
- Customise stages, triggers, and surfaces

**Step 9 — Deployment**
- Static site preview (iframe)
- Push to GitHub
- Deployment status and URL

#### Screen 4: Simulation Management (live monitoring)

- **Student Activity** — active students, recent logins, booking counts, chat sessions
- **Content Management** — edit documents, update prompts, manage visibility rules
- **Visibility Timeline** — visual timeline showing when content unlocks per unit
- **Analytics** — booking statistics, employee coverage, engagement metrics
- **Student Management** (individual-account mode) — student list, password reset, journey reports, data export
- **Git Operations** — view commit history, view diff against last deployment

### 10.3 Data Operations Summary

| Operation | How It Works |
|-----------|-------------|
| Create simulation | Dashboard creates repo on GitHub, clones to VPS, scaffolds YAML from wizard answers, runs generator, commits + pushes |
| Edit simulation config | Dashboard edits YAML in working clone, regenerates dist/, commits + pushes; updates DB cache |
| Add employee | Dashboard creates employee record → generates prompt → provisions AnythingLLM workspace (if available) → updates booking config |
| Edit backstory | Dashboard updates prompt → updates AnythingLLM workspace → regenerates chatbot page |
| Add document | Dashboard stores document → uploads to relevant AnythingLLM workspaces (if RAG-enabled) |
| Set visibility rule | Dashboard creates rule → API enforces on next student request |
| Clone simulation | Dashboard creates new repo on GitHub, copies content from source, registers new simulation owned by cloner |
| Archive simulation | Sets status to `archived` → site remains accessible but dashboard is read-only |

### 10.4 The Lay-Person Wizard

The wizard is the entry path for non-technical UCs. It asks plain-language questions:

- "What's your fictional company called?"
- "What industry is it in?" (dropdown with descriptions)
- "What's the scenario or situation?" (dropdown: breach, growth, crisis, custom...) "Or describe a custom scenario:" (text)
- "Who are the key people students will interact with?" (form repeated per employee, with optional LLM-assist for backstories)
- "What documents do students need to read?" (form per document, with optional LLM generation)
- "Who is your audience?" → triggers the §7 audience selection

The wizard outputs YAML to the simulation repo. The UC never sees raw YAML unless they want to. Power users can skip the wizard and edit YAML directly in their git client (the dashboard pulls before each subsequent operation).

### 10.5 LLM-Assisted Features

The "LLM-assist" button is available on:

| Field | What the LLM Does |
|-------|-------------------|
| Company description | Generates a 2–3 paragraph description from name, industry, scenario |
| Employee backstory | Generates a backstory stub from archetype, role, company context, scenario |
| Scenario narrative | Generates a narrative with tensions from scenario type and company type |
| Document draft | Generates a policy/procedure draft from document type, company context, scenario |
| Culture definition | Generates tone, values, communication norms from industry and company size |
| Chatbot prompt review | Reads a generated prompt and suggests improvements |

LLM-assist is always optional. The UC can write everything manually. The LLM provides first drafts, not final content.

In `audience: minors` mode, LLM-assist is disabled by default and requires per-use confirmation.

### 10.6 Bulk Generation at Simulation Creation

Distinct from the per-field LLM-assist button (§10.5), the wizard offers **bulk generation at creation time**. This is where Ensayo earns its keep — turning a 5-minute conversation into a complete simulation rather than days of authoring.

**Default behaviour:**

| Audience | LLM provider configured | Default at creation |
|----------|------------------------|---------------------|
| `adults` | Real provider (Anthropic / OpenRouter / Ollama / Gemini / OpenAI) | **Bulk-generate ON** — all backstories, documents, scenario narrative, culture definition produced in one pass |
| `adults` | Stub only (or no provider) | Skeleton templates — UC fills in manually |
| `minors` | Any | **Bulk-generate OFF** — skeleton templates with optional per-item LLM-assist requiring confirmation |

**Wizard flow with bulk-generate ON:**

1. UC answers framing questions (company name, industry, scenario type, audience, employee count, document categories needed)
2. Wizard previews scope and **shows estimated token usage**: *"This will generate ~10 backstories, ~15 documents, 1 scenario narrative, 1 culture definition. Estimated ~60k input tokens, ~40k output tokens with the configured provider (`anthropic/claude-sonnet-4-6`). Check your provider's pricing for current rates; Ollama and stub modes are free."* The wizard does not maintain a per-provider price table — provider prices change too often, and rolling out a platform release just to refresh prices isn't worth it. UC looks up their provider's current rate.
3. UC clicks **"Generate everything"** (default) or **"Skip — I'll write it manually"**
4. The dashboard POSTs to `/api/v1/jobs/bulk-generate` and gets back a `job_id`. The wizard shows a spinner with current progress text and polls `GET /api/v1/jobs/{job_id}/status` every 2 seconds. Status returns `{state: running|done|failed, progress: "8 of 25", current_item: "Marcus Webb (head of service delivery)", items_completed: [...]}`. When state flips to `done`, the wizard fetches the full results.
5. UC reviews each item. Per-item actions: edit inline, **"Regenerate this one"** (with optional new prompt hint), accept
6. UC saves. YAML is written, first commit pushed, GitHub Pages deployment kicks off.

**Why default ON for adults:**

The original problem Ensayo solves is "hand-writing 47 employees + 31 documents takes weeks." If a non-technical UC has to click a generate button on each of 78 individual items, the wizard offers no leverage over manual authoring. Bulk generation is where the time-to-value lives. Cost transparency at step 2 prevents surprise bills.

**Why default OFF for minors:**

The §7 audience-mode safety bundle requires every piece of LLM-generated content to be explicitly reviewed by an instructor before reaching a student. Defaulting bulk-generate to OFF in minors mode forces the per-item review step into the workflow. UCs who do want LLM help in minors mode get it on a per-item basis with a confirmation dialog.

**Cost transparency:**

The dashboard estimates **token usage** (input + output) but does not estimate cost in dollars. Provider prices change too frequently for a maintained table to be reliable; the UC looks up their provider's current rate against the token estimate. Ollama and stub modes report "free." Estimates are conservative — actual usage is usually lower because not every generated item hits maximum tokens. After generation completes, the dashboard reports actual token usage so UCs can true up against their bill.

**Failure handling:**

If bulk generation fails partway through (network error, rate limit, provider outage), the wizard saves successfully-generated items and offers **"Continue from where it stopped"** when the UC retries. No re-paying for already-generated content.

**Regeneration after creation:**

After the simulation exists, the UC can re-run bulk generation on a subset (e.g. "regenerate all employees in the marketing department" or "regenerate the breach-response policy"). The dashboard exposes this under Simulation Management → Content → "Bulk regenerate." Regenerated content overwrites the previous YAML; git history preserves the original.

### 10.7 Two-Layer Configuration

Pattern from workready-api: configuration lives in two layers, each appropriate to a different person and timeframe.

| Layer | What it controls | Set by | Where it lives | Reload semantics |
|-------|-----------------|--------|----------------|------------------|
| **Instance env** | Behavioural tuning shared across simulations: business hours defaults, lazy-delivery delays/jitter, lunchroom timing, blocking model, max-cycles, LLM provider keys, SMTP credentials, GitHub token | Instance admin | `.env` and `instance.env` on the VPS | Restart the API service |
| **Per-simulation YAML** | Content + simulation-scoped overrides: company facts, employees, scenario, audience mode, theme, workflow choice, **and per-simulation overrides of any instance-env tuning knob** | UC via dashboard or direct YAML edit | `company.yaml` / `simulation.yaml` in the simulation repo | Picked up at next generator run / next API request |

**Examples of per-simulation overrides:**

```yaml
# In simulation.yaml — overrides instance defaults for this simulation only
scheduling:
  business_hours: {start: 8, end: 16, days: [1,2,3,4]}   # cohort runs shorter days
  feedback_delay_minutes: 30                              # this cohort wants faster feedback
  slot_duration_minutes: 45                               # longer interview slots

workflow:
  max_cycles: 1                                           # this cohort gets one shot, no re-application
  blocking:
    on_resume_failure: company                            # stricter than instance default

lunchroom:
  beat_interval_seconds: 90                               # slower pacing for this audience
  hard_cap: 8
```

**Resolution order:** per-simulation YAML > instance env var > built-in default.

**Why two layers:**
- Instance admin should not have to edit YAML for every simulation to set sensible defaults — they set them once in `.env` and every simulation inherits.
- UCs should not have to touch `.env` (they may not have shell access on the VPS) — they override per simulation in the dashboard, which writes to YAML.
- Different cohorts in the same institution may want different pacing without redeploying the instance.
- Audience mode and safe-mode constraints are per-simulation, naturally.

**The dashboard surfaces tuning knobs in the simulation configuration wizard** under an "Advanced" or "Pacing & Behaviour" tab. Defaults shown reflect the current instance env values; the UC sees what they're overriding.

---

## 11. Student-Facing Simulation

### 11.1 What a Generated Site Looks Like

A generated simulation site is a corporate website that students explore. Two layers:

**Public layer** (always accessible):
- Homepage, About, Services/Products, Contact, Press/Blog

**Internal layer** (gated by authentication):
- Staff directory, employee chatbot pages, document library, internal pages, booking calendar

In multi-site simulations, students additionally interact with a Student Portal (§11.5).

### 11.2 Navigation Structure

```
Home
├── About
│   ├── Company History
│   ├── Leadership Team
│   └── Mission & Values
├── Services / Products
├── Contact
├── Blog / Press
│
├── [Staff Portal] ← auth gate
│   ├── Staff Directory
│   │   └── {Employee Name} ← chatbot page
│   ├── Documents
│   │   ├── Policies / Procedures / Reports & Data
│   └── Internal Tools
│       ├── Org Chart
│       └── Booking Calendar
│
└── [Student Portal] ← multi-site only
    ├── Dashboard
    ├── Inbox
    ├── My Tasks
    └── Journey Report
```

### 11.3 Interactivity Delivery

| Feature | Delivery |
|---------|----------|
| Page navigation | Standard HTML links |
| Document viewing | Static HTML pages |
| Employee profiles | Static HTML pages |
| Chatbot (keyword) | Client-side JS reading `keywords.json` |
| Chatbot (LLM via AnythingLLM) | AnythingLLM embed widget |
| Chatbot (LLM via proxy) | Static page calls `/api/v1/chat/{employee_id}` on VPS |
| Booking | Modal JS calling VPS API |
| Auth gate | VPS API session verification |
| Timed content release | VPS-enforced visibility rules |
| Task submission | VPS API with file upload |
| Inbox / portal | VPS API; portal page renders |

### 11.4 Chatbot Interaction Flow

**LLM mode (via AnythingLLM):**
```
Student visits employee page
  → page loads AnythingLLM embed widget
  → widget connects to AnythingLLM workspace
  → system prompt + RAG docs define employee's knowledge and personality
  → student types message → AnythingLLM processes → reply rendered in widget
```

**LLM mode (via proxy):**
```
Student visits employee page
  → page loads chat UI
  → student types message → JS POSTs to /api/v1/chat/{employee_id}
  → API loads system prompt from DB
  → API calls configured LLM provider
  → reply returned and rendered
```

**Keyword mode:**
```
Student visits employee page
  → page loads chatbot-keywords.js
  → JS loads keywords.json for this employee
  → student types message → JS matches keywords → response rendered
  → no network requests needed
```

### 11.5 Student Portal (Multi-Site Mode)

In multi-site simulations, students interact with a central portal providing:

- **Dashboard** — current application status, active stage, next actions
- **Personal inbox** — system notifications
- **Work inbox** — messages from virtual employees
- **Conversation views** — LLM-driven dialogues (interviews, coaching, consultations)
- **Task view** — active tasks with submission forms, review status, progressive reveal
- **Group chat view** — multi-participant conversations (lunchroom, ward round, trading floor)
- **Journey report** — printable summary of the entire student experience

The portal is a single-page HTML/JS application served from the multi-site simulation's repo at the root path (`/`). Company sites live at subpaths (`/nexuspoint/`, `/ironvale/`, etc.). The portal polls the API for state changes and renders the appropriate view.

### 11.6 Booking-Gated Chatbot Flow

```
Student visits employee chatbot page
  → chatbot-booking.js checks if student has a valid booking
  → No booking?
    → "Schedule a Meeting" button shown
    → Booking modal opens (calendar UI, slot picker)
    → Student selects slot
    → JS calls POST /api/v1/bookings/
    → Booking confirmed, ICS file downloaded
    → Chat widget revealed
  → Has booking?
    → "Start Meeting" button shown
    → Student clicks → chat widget activated
```

### 11.7 Optional: Interactive Primer

A **primer** is an optional pre-simulation onboarding component — a short interactive-fiction story (~10–15 minutes) that walks a student through the workflow shape before they engage with the real simulation. Pattern adopted from `workready-primer/`.

**Why it exists:** for advanced multi-site simulations with several distinct interaction surfaces, students benefit from a "safe-to-fail rehearsal" of the workflow itself. They get a feel for *how* the simulation works (browse → apply → interview → tasks → reflection) without spoiling the *content* of the actual scenario. After each decision, "shadow paths" show what would have happened with alternative choices.

**Architecture:**

```
sim-repo/
├── primer/                       # optional
│   ├── primer.ink                # source — Ink narrative language
│   ├── primer.ink.json           # compiled — committed to repo
│   ├── lib/ink.js                # vendored inkjs runtime
│   ├── index.html                # static player, ~150 lines vanilla JS
│   └── tone-variants.yaml        # warm / professional / playful tone tags
└── dist/
    └── primer/                   # served at /primer/ subpath of the simulation site
```

The primer is pure static — no server, no LLM, no API. Branching narrative + shadow paths only. Deploys with the rest of the simulation to GitHub Pages.

**Generation:**

Ensayo ships **primer templates per workflow type** (`internship-primer.ink`, `medical-network-primer.ink`, `financial-markets-primer.ink`). The generator parameterises the template with the simulation's company names, role titles, and scenario keywords — but the workflow shape and shadow-path mechanic are template-fixed, not LLM-generated. UCs edit the resulting `.ink` file in any text editor or in [Inky](https://github.com/inkle/inky) (the official Ink editor).

**Build pipeline:**

```
ensayo primer build (called by dashboard or CLI):
  1. Read primer.ink
  2. Run inkjs compiler → primer.ink.json
  3. Copy vendored ink.js + index.html
  4. Output to dist/primer/
  5. Commit + push (alongside the main simulation build)
```

**When to include a primer:**

| Simulation type | Recommend primer? |
|-----------------|-------------------|
| Single-company, light-touch (CloudCore-style document study) | Probably not |
| Single-company with bookings + LLM chatbots | Optional |
| Multi-site internship / healthcare / financial | Yes — multiple surfaces benefit from rehearsal |
| Minors-audience simulation | Optional, kept very simple |

**Scope and phasing:**

- **MVP (Phases 0–7):** No primer. The platform works fine without it.
- **Phase 8 (multi-site):** Ship one primer template (`internship-primer.ink`) derived from `workready-primer/`. The generator wires primer into multi-site builds when the UC opts in via `simulation.yaml`.
- **Later phases:** Additional primer templates per workflow type.

**Tone variants** (from workready-primer): three parallel tones — warm / professional / playful — selected by the student at the title screen. Authoring guidance: keep all three in sync. LLMs are good at this; humans tend to update only one.

**LMS embedding:** primers are framework-agnostic static HTML, so they can be embedded in Blackboard / Canvas / Moodle as raw HTML or wrapped as a SCORM package. Completion is signalled via `window.postMessage` to the parent frame.

---

## 12. Multi-Site Simulation

### 12.1 Repo Layout

One repo per simulation. Multi-site uses a structured layout:

```
acme-internship-sim/
├── simulation.yaml             # Multi-site coordination
├── workflow.yaml               # Lifecycle stages
├── companies/
│   ├── nexuspoint/
│   │   ├── company.yaml
│   │   └── content/
│   │       ├── employees/
│   │       └── docs/
│   ├── ironvale/
│   └── ...
├── portal/
│   └── portal.yaml             # Student portal config
└── dist/
    ├── index.html              # Portal entry
    ├── jobs/                   # Directory/board view
    ├── nexuspoint/             # Company subpath
    │   └── index.html, etc.
    ├── ironvale/
    └── ...
```

### 12.2 URL Structure

Default: subpath multi-site at one custom domain.

- Portal: `https://acme-sim.eduserver.au/`
- Job board: `https://acme-sim.eduserver.au/jobs/`
- Company sites: `https://acme-sim.eduserver.au/nexuspoint/`, `/ironvale/`, etc.

**Trade-off vs WorkReady's per-company domains:** Less realism (students see "acme-sim.eduserver.au/nexuspoint/" rather than "nexuspoint.eduserver.au"). Mitigated by strong per-company branding (logo, theme, copy) so the subpath feels like a navigation context rather than a different domain.

**Future work:** Per-site domains via separate repos. Adds dashboard complexity for coordinated multi-repo edits and DNS overhead. Not in MVP. Tracked as a future enhancement.

### 12.3 Interaction Surfaces

WorkReady implements six distinct interaction surfaces, each backed by its own database table, API routes, and portal UI. These surfaces are **domain-independent building blocks** that can be composed differently for different simulation types.

| Surface | WorkReady Implementation | General Pattern |
|---------|------------------------|-----------------|
| **In-app messaging** | Dual inbox (personal + work) with lazy-delivery messages from virtual employees and the system | Any simulation where students receive communications from virtual people. Messages with `deliver_at` timestamps provide "this arrives later" without background workers |
| **1-on-1 conversation** | Hiring interview (~10 turns), mid-placement coaching (~5 turns), exit interview (~8 turns) | Any structured dialogue between a student and one virtual employee: consultations, audits, performance reviews, patient interviews, regulatory inspections |
| **Group conversation** | Lunchroom — multi-participant chat, pre-planned beat arcs, lazy delivery, `@mentions` reschedule beats | Any multi-person conversational scenario: team meetings, board meetings, ward rounds, trading floor, committee hearings, project stand-ups |
| **Document submission and review** | Work tasks — student submits PDF or text, LLM reviews, lazy-delivered structured feedback. Progressive reveal | Any workflow producing student work: reports, analyses, designs, treatment plans, compliance audits, investment memos |
| **Booking / scheduling** | Tiered availability, business hours, slot generation, random rescheduling, ICS generation. Used to gate chatbot access | Any time-based interaction gate: meetings, consultations, equipment booking, session registration |
| **Assessment / evaluation** | Resume assessment, interview assessment, task assessment. Journey report aggregates all results | Any automated evaluation of student work |

**Key principle:** These surfaces are *composable*. A simulation doesn't need all six. A simple single-company sim might use only booking + 1-on-1 conversation. A complex multi-site sim might use all six.

#### Lazy Delivery Pattern

All time-dependent behaviour uses the same pattern:

- Write a row with a `deliver_at` ISO timestamp
- On read, filter `WHERE deliver_at <= now()`
- **No background workers, no job queues, no cron**
- The student's browser polls; the server evaluates on each request

This is a deliberate architectural choice that eliminates an entire class of infrastructure complexity.

### 12.4 Configurable Lifecycle (Workflow Engine)

WorkReady hardcodes a six-stage internship lifecycle. Ensayo generalises this into **configurable workflows** composed from the interaction surfaces above.

A workflow is an ordered list of stages, where each stage activates one or more surfaces. Stages advance based on triggers (completion, time, condition).

```yaml
# Example: Internship workflow (WorkReady)
workflow:
  stages:
    - name: browse
      hub_view: job_board
      surfaces: [in_app_messaging]
      trigger: student_applies
      advance_to: resume

    - name: resume
      surfaces: [assessment, in_app_messaging]
      trigger: assessment_complete
      on_pass: interview
      on_fail: rejected
      blocking: role

    - name: interview
      surfaces: [booking, one_on_one_conversation, assessment, in_app_messaging]
      conversation_kind: hiring_interview
      trigger: conversation_complete
      on_pass: placement
      on_fail: rejected
      blocking: company

    - name: placement
      surfaces: [document_submission, in_app_messaging]
      tasks: 3
      progressive_reveal: true
      trigger: all_tasks_complete
      advance_to: exit
      mid_event:
        trigger: task_2_reviewed
        surfaces: [one_on_one_conversation]
        conversation_kind: coaching_session
        also_trigger: task_reviewed
        also_surfaces: [group_conversation]

    - name: exit
      surfaces: [one_on_one_conversation, assessment, in_app_messaging]
      conversation_kind: exit_interview
      trigger: conversation_complete
      advance_to: completed

  terminal_states: [completed, rejected, resigned]
  max_cycles: 3
```

Other workflow examples (medical placement, financial markets) are in §12.5. The workflow definition is part of the simulation configuration — the API does not hardcode any specific workflow.

**The declarative workflow engine is validated by a Phase-7 spike** (§14) before multi-site implementation commits, to confirm the YAML schema can express at least one non-internship workflow end-to-end.

### 12.5 Multi-Site Examples

Three domains validate the architecture.

#### Internship (WorkReady — implemented as reference)

| Aspect | Detail |
|--------|--------|
| Domain | Business / Marketing / Management |
| Hub | Internship portal with job board |
| Sites | 6 fictional companies across industries |
| Student role | Intern applicant → intern |
| Surfaces | All six |
| Lifecycle | Browse → Resume → Interview → Placement (3 tasks + coaching + lunchroom) → Exit |

#### Healthcare Network (proposed, requires content)

| Aspect | Detail |
|--------|--------|
| Domain | Nursing / Medicine / Pharmacy / Allied Health |
| Hub | Hospital/clinic portal with specialist directory |
| Sites | 4–6 departments (Emergency, Pharmacy, Radiology, Physiotherapy, Pathology, GP) |
| Student role | Junior clinician on rotation |
| Surfaces | All six |
| Lifecycle | Orientation → Consultation → Treatment Plan → Handoff → Review |
| Content gap | Medical-domain document templates and clinical-role archetypes need authoring |

#### Financial Markets (proposed, requires content)

| Aspect | Detail |
|--------|--------|
| Domain | Finance / Investment Analysis |
| Hub | Exchange board with simulated price feeds |
| Sites | 4–8 listed companies plus regulator and broker |
| Student role | Junior analyst at a fund |
| Surfaces | All six |
| Lifecycle | Market Open → Analysis → Investor Pitch → Trading → Board Report |
| Content gap | Financial-domain templates, market-data CSV time series, regulatory document types |

### 12.6 What These Examples Prove

| Requirement | Internship | Healthcare | Financial |
|-------------|-----------|------------|-----------|
| Multi-site (different themes per site) | ✅ | ✅ | ✅ |
| Central hub | ✅ Job board | ✅ Specialist directory | ✅ Exchange board |
| Lazy-delivery messaging | ✅ | ✅ Referral letters | ✅ Internal memos |
| 1-on-1 LLM conversation | ✅ Interview | ✅ Consultation | ✅ Management meeting |
| Group conversation | ✅ Lunchroom | ✅ Ward round | ✅ Trading floor |
| Document submission + LLM review | ✅ Work tasks | ✅ Clinical notes | ✅ Research reports |
| Booking | ✅ Interviews | ✅ Appointments | ✅ Earnings calls |
| Timed content release | ✅ Task reveal | ✅ Lab results | ✅ Quarterly filings |
| Assessment | ✅ Resume, tasks | ✅ Clinical reasoning | ✅ Analysis quality |
| Cross-site navigation | ✅ Portal ↔ company | ✅ Department ↔ department | ✅ Broker ↔ company |

The interaction surfaces are identical across domains. What changes:
1. **The workflow** (stages, surface activation, triggers)
2. **The content** (document templates, role archetypes, scenario narratives)
3. **The hub presentation** (job board vs specialist directory vs exchange board)

This confirms the architectural decision: the platform provides a fixed set of interaction surfaces and a configurable workflow engine. Domain specificity lives in content and configuration, not in platform code.

### 12.7 Hub Types

| Hub Type | Narrative | Student Role | Directory View |
|----------|-----------|-------------|----------------|
| `internship` | Structured internship program | Intern applicant | Job board |
| `consulting_firm` | Consultant working across clients | Consultant | Client list |
| `medical_network` | Clinician on rotation | Junior clinician | Specialist directory |
| `financial_markets` | Analyst at a fund | Junior analyst | Exchange board |
| `job_board` | Pure job marketplace | Job seeker | Job listings |
| `portal` | Generic access point | Explorer | Link list |

### 12.8 Configuration

```yaml
simulation:
  name: "WorkReady Internship Program"
  slug: "workready"
  type: multi_site
  audience: adults
  auth_mode: email_only

  portal:
    name: "WorkReady Portal"
    theme: "portal-clean"

  hub:
    type: internship
    narrative: |
      You are a student participating in an internship program...

  workflow:
    stages: [browse, resume, interview, placement, exit]
    # ... full workflow definition

  blocking:
    on_resume_failure: role
    on_interview_failure: company
    on_task_failure: none

  scheduling:
    timezone: "Australia/Perth"
    business_hours: {start: 9, end: 17, days: [1,2,3,4,5]}
    slot_duration_minutes: 30
    feedback_delay_minutes: 120

  llm:
    provider: anthropic
    model: claude-sonnet-4-6

  companies:
    - company: nexuspoint-systems
    - company: ironvale-resources
    - company: meridian-advisory
    - company: metro-council-wa
    - company: southern-cross-financial
    - company: horizon-foundation
```

### 12.9 Generation

When generating a multi-site simulation:

1. The generator reads `simulation.yaml` and each referenced `companies/*/company.yaml`
2. It generates each company site under `dist/{company-subpath}/`
3. It generates the portal site at `dist/`
4. It generates the directory/board at `dist/jobs/` (or equivalent)
5. It produces a central configuration linking all sites
6. The Ensayo Services component is configured with company slugs, subpaths, workflow definition, and scheduling parameters

### 12.10 WorkReady → Ensayo Surface Mapping

For implementors familiar with WorkReady:

| WorkReady Code | Generalised Surface | DB Table (WorkReady) | DB Table (Ensayo) |
|---------------|---------------------|---------------------|-------------------|
| `interview.py` (`kind='hiring'`) | 1-on-1 conversation | `interview_sessions` | `conversation_sessions` |
| `performance_review.py` | 1-on-1 conversation | `interview_sessions` | `conversation_sessions` |
| `exit_interview.py` | 1-on-1 conversation | `interview_sessions` | `conversation_sessions` |
| AnythingLLM workspace (hiring desk) | Chatbot | External | `employees.chatbot_workspace_id` |
| `notifications.py` + `mail.py` | In-app messaging | `messages` + `message_attachments` | `messages` |
| `task_reviewer.py` + `placement.py` | Document submission & review | `tasks` + `task_submissions` | `task_instances` + `task_submissions` |
| `lunchroom.py` + `lunchroom_chat.py` | Group conversation | `lunchroom_sessions` + `lunchroom_posts` | `group_chat_sessions` + `group_chat_posts` |
| `assessor.py` (resume) | Assessment | `stage_results` | `task_submissions.assessment_json` + `conversation_sessions.assessment_json` |
| `journey_report.py` | Journey report (read model) | Aggregates from multiple tables | Same — computed from session/task/message records |
| `blocking.py` | Blocking model | Derived from application history | Same pattern, configurable per workflow |
| `scheduling.py` | Booking & scheduling | `interview_bookings` + `calendar_events` | `bookings` |

**Key WorkReady pattern preserved:** The `kind` column on `interview_sessions` distinguishes `hiring`, `exit`, `performance_review` — three conversation surfaces sharing one table. Ensayo generalises this: `conversation_sessions.kind` can be any string defined by the workflow (`hiring_interview`, `coaching_session`, `clinical_consultation`, `investor_pitch`). New kinds don't require schema changes.

### 12.11 Optional: External Tool Export Endpoints

Pattern adopted from workready-api's Talk Buddy and Career Compass integrations. Ensayo exposes per-application and per-session **export endpoints** that return stable JSON snapshots of student state. Any external tool — rehearsal apps, gap-analysis tools, gradebook integrations, analytics dashboards — can consume these endpoints without coupling to internal schema.

**Standard endpoints (all optional, opt-in per simulation):**

| Endpoint | Returns | Use case |
|----------|---------|----------|
| `/api/v1/export/application/{id}.json` | Full application state: stages completed, assessments, transcripts, notes | Gradebook export, archival |
| `/api/v1/export/conversation/{session_id}.json` | Single conversation transcript with metadata (kind, persona, turns, assessment) | Rehearsal app import (e.g. Talk Buddy) |
| `/api/v1/export/group-chat/{session_id}.json` | Group chat session with all posts, beat plan, participation notes | Group conversation rehearsal |
| `/api/v1/export/journey/{application_id}.json` | Aggregated journey report (everything that happened, in chronological order) | LMS submission, lecturer review, portfolio |
| `/api/v1/export/cohort/{simulation_id}.csv` | Aggregated cohort metrics (pass rates, time-to-completion, surface engagement) | Lecturer analytics |

**Stable schema contract:**

Each export endpoint returns a JSON document with:
- `schema_version`: integer (incremented on breaking changes)
- `simulation`: { id, slug, name, type }
- `student`: { id (or null in shared-password mode), email (or null) }
- `payload`: the entity-specific data

External tools pin `schema_version` and adapt to schema changes explicitly. Schema additions (new fields) do not require a version bump; schema removals or semantic changes do.

**Authorisation:**

Two access modes per endpoint:
- **Student-facing**: the student authenticates and exports their own data only (e.g. for a "Practice in Talk Buddy" button on the portal)
- **Lecturer-facing**: the UC authenticates with their dashboard token and exports any simulation they own (cohort exports, gradebook integration)

**WorkReady-specific examples (generalised):**

- The "Practice in Talk Buddy" button on the WorkReady interview pre-screen calls `/api/v1/export/conversation/{id}.json` and passes the result to a local Electron app via download or copy-paste. In Ensayo, this is the same endpoint with a `format=talk-buddy` query parameter for tool-specific shaping if needed.
- Career Compass consumes a resume + job-description pair. In Ensayo, this becomes `/api/v1/export/application/{id}.json?include=resume,job` and any external gap-analysis tool can consume it.

**Scope and phasing:**

- **MVP (Phase 3):** No export endpoints. Internal use only.
- **Phase 5 (individual accounts):** Add per-application and per-conversation exports. Required for any institutional integration.
- **Phase 8 (multi-site):** Add cohort and journey-report exports.
- **Future (Phases 2/3 of v2 spec roadmap as referenced in the original WorkReady SYSTEM.md):** Inbound integrations (LMS gradebook pass-back, Curtin SSO, MS Teams via Graph API) — not in scope for the initial 26-week roadmap.

---

## 13. Document and Content Library

### 13.1 Base Library Structure

The Ensayo repo ships with a base library:

```
content-library/
├── industries/
│   ├── cloud_services.yaml
│   ├── event_management.yaml
│   ├── retail.yaml
│   ├── managed_it.yaml
│   ├── healthcare.yaml
│   ├── mining.yaml
│   ├── finance.yaml
│   ├── local_government.yaml
│   ├── software_development.yaml
│   └── not_for_profit.yaml
├── archetypes/
│   ├── founder_ceo.yaml
│   ├── operations_manager.yaml
│   ├── finance_manager.yaml
│   ├── marketing_manager.yaml
│   ├── hr_manager.yaml
│   ├── client_relations.yaml
│   ├── technical_specialist.yaml
│   ├── compliance_officer.yaml
│   ├── sales_manager.yaml
│   ├── project_manager.yaml
│   ├── software_engineer.yaml
│   ├── product_manager.yaml
│   └── devops_engineer.yaml
├── scenarios/
│   ├── breach.yaml
│   ├── growth.yaml
│   ├── digital_transformation.yaml
│   ├── crisis.yaml
│   ├── merger.yaml
│   └── product_launch.yaml
├── document_templates/
│   ├── policies/
│   ├── procedures/
│   ├── reports/
│   └── data/
└── themes/                     # Each theme is a full Astro package
    ├── portal-clean/            # ← derived from workready-portal
    │   ├── package.json
    │   ├── package-lock.json
    │   ├── astro.config.mjs
    │   ├── theme.yaml           # declares supported page kinds + content props
    │   └── src/
    │       ├── pages/
    │       ├── layouts/
    │       ├── components/
    │       └── styles/
    ├── directory/               # ← derived from workready-jobs
    ├── tech-modern/             # ← derived from nexuspoint-systems
    ├── mining-rugged/           # ← derived from ironvale-resources
    ├── nfp-warm/                # ← derived from horizon-foundation
    ├── finance-traditional/     # ← derived from southern-cross-financial
    ├── government-formal/       # ← derived from metro-council-wa
    └── advisory-cool/           # ← derived from meridian-advisory
```

The eight initial themes are derived from the existing hand-built WorkReady sites. Each theme retains the bespoke visual language of its source — distinct typography, palette, layout, and component choices — but the WorkReady-specific content is decoupled. A theme is the visual identity; the company's `company.yaml` provides the content.

### 13.2 Content Resolution at Generation Time

**Critical principle: base library content is COPIED into the simulation's YAML at creation time, not referenced live.**

When generating a new simulation:

1. The wizard or YAML references a base library item (e.g. `archetype: founder_ceo`)
2. The generator EXPANDS the reference: copies the archetype's fields into the simulation's YAML
3. After expansion, the simulation owns its bytes — it does not reference the base library at runtime

```
Base library at creation time:
  archetypes/founder_ceo.yaml
    personality: [decisive, detail-oriented, hands-on]
    knowledge_areas: [strategy, finance, operations]
    ...

UC selects "founder_ceo" archetype for employee Sarah Chen:
  ↓ generator expands
  
Simulation's company.yaml:
  employees:
    - name: Sarah Chen
      archetype: founder_ceo  # marker for traceability
      personality: [decisive, detail-oriented, hands-on]  # COPIED IN
      knowledge_areas: [strategy, finance, operations]    # COPIED IN
      ...
```

**Implications:**
- Updating the Ensayo base library does NOT retroactively change existing simulations
- Simulations are portable — clone the repo to a different Ensayo instance, it still works
- A UC who customises a base archetype is editing their own copy, not the shared library
- No "library version drift" between simulations on the same instance

### 13.3 Per-Unit Customisation in Multi-UC Simulations

When a simulation is shared by multiple UCs (one is owner, others are co-coordinators), per-unit customisation works through visibility rules:

| Need | Mechanism |
|------|-----------|
| Hide an employee for one unit | Co-coordinator adds visibility rule `hide employee/marcus for unit ISYS6018`. Other units still see Marcus. |
| Add a unit-specific document | Co-coordinator adds the document with `unit_code: ISYS6018`. Only that unit sees it. |
| Modify shared content | Only the owner can edit. Co-coordinators request changes from the owner. |
| Diverge significantly | Co-coordinator clones the simulation. The clone is independent. |

This avoids the need for git branching. There is one canonical YAML per simulation; per-unit differences are layered visibility rules. When a co-coordinator's needs exceed what visibility rules can express, the answer is "clone the simulation" — and the dashboard makes that a one-click action.

### 13.4 Versioning and Updates

**Existing simulations are frozen against the base library version they were created against.** Their YAML is immutable from upstream's perspective.

**When the Ensayo project releases an updated base library:**
- Existing simulations are unaffected
- New simulations created after the update receive the new base library
- A UC who wants the new version of an updated base item must hand-merge it (e.g. copy the new archetype YAML into their simulation's YAML) OR scaffold a new simulation

**No auto-pull mechanism is provided.** Predictability for live cohorts beats convenience. A simulation running with students mid-semester will not change underneath them because of an upstream release.

**Communication:** When the platform author updates the base library, an instance-admin notification appears in the dashboard ("Ensayo 1.4 includes 3 new archetypes and 1 updated scenario template — affects new simulations only"). UCs can review the diff and decide whether to manually port changes.

### 13.5 Per-Scenario Overrides

A scenario can override or extend any base library content at creation time:

```yaml
# In company.yaml
documents:
  - type: policy
    title: "Information Security Policy"
    source: template                    # Use the base library template at scaffold
    customise:
      add_sections: ["breach_response"]
  - type: support
    title: "Incident Report — September 2024"
    source: custom                      # UC-authored
    content: "..."
  - type: data
    title: "Customer Records Export"
    source: generated                    # LLM-generated from template
    brief: "Generate 200 realistic customer records..."
```

After expansion, all three documents are stored as full Markdown/text in the simulation's repo. The `source` field is metadata (for the dashboard to know how it was created); the content itself is owned by the simulation.

### 13.6 Timed Release Mechanism

Documents, chatbot access, and pages can be released on a schedule. All visibility is server-enforced by the VPS API.

**Time-based release:**
```yaml
visibility_rules:
  - target: document/incident-report-sept-2024
    action: show
    at: "2026-03-15T09:00:00+08:00"

  - target: chatbot/marcus-webb
    action: show
    relative_to: scenario_start
    offset_days: 14

  - target: document/budget-2025
    action: hide
    at: "2026-05-01T17:00:00+08:00"
```

**Condition-based release:**
```yaml
visibility_rules:
  - target: chatbot/cto-amina
    action: show
    condition: booking_completed
    with: employee/alex-nguyen
```

**Implementation:** The API checks visibility rules on every gated request. Students cannot bypass server-side gating.

### 13.7 Theme Architecture

Each theme is an Astro package — a self-contained mini-project with its own `package.json`, dependencies, components, and pages. The generator's job is to feed company/simulation YAML into the theme as Astro content collections, then run the theme's build.

**Theme contract:**

A theme must declare in `theme.yaml`:

```yaml
name: tech-modern
display_name: "Tech Modern"
description: "Clean blue/grey palette, sans-serif, generous whitespace. Suits SaaS, cloud, and tech companies."
preview_image: preview.png

# Which page kinds this theme implements
supports:
  - home
  - about
  - services
  - contact
  - employee
  - document_library
  - document
  - staff_directory

# Which features can render inside this theme
features:
  chatbot_widget: true       # can embed AnythingLLM widget or keyword JS
  booking_modal: true        # can render booking-modal.js
  portal: false              # not a portal theme — use portal-clean for that
  directory: false           # not a directory theme — use directory for that

# What sections of company.yaml this theme reads
content_props:
  - company.name
  - company.tagline
  - company.description
  - company.branding
  - employees[]
  - documents[]
```

**Theme compatibility is advisory, not blocking.** When a UC selects a configuration that the chosen theme's `supports:` declaration does not include (e.g. picking `tech-modern` then enabling the `group_chat` surface that theme doesn't render), the dashboard:

1. **Suggests** a more compatible theme via the wizard's recommendation engine ("Themes that support `group_chat`: `portal-clean`, `advisory-cool`")
2. **Allows the UC to proceed** with their choice — overrides are not blocked
3. **Logs a warning** to the audit log and observability stream ("UC alex@uni.edu chose theme `tech-modern` for simulation `acme` despite missing support for `group_chat`")

The override outcome is the UC's responsibility — the rendered site may have layout issues, missing components, or fall back to generic markup. If override warnings cluster around specific theme/surface combinations across many simulations, the platform team uses that as a signal to extend the theme's `supports:` declaration in the next platform release. Friction = signal for iteration, not a hard wall for the user.

**Build pipeline:**

```
ensayo build --simulation acme/
  ↓
1. Read company.yaml and content/*
2. Look up theme name → resolve to themes/tech-modern/
3. Copy theme package into working dir as build/
4. Generate Astro content collection files in build/src/content/
   (one entry per employee, one per document, one per page)
5. Run `npm ci && npm run build` in build/
6. Move build/dist/ to acme/dist/
7. Discard build/ working tree
```

**Adding a new theme:**

1. Copy an existing theme as a starting point: `cp -r themes/tech-modern themes/my-new-theme`
2. Edit `theme.yaml` with new name, description, supports, features
3. Modify `src/pages/`, `src/components/`, `src/styles/` to express the new visual language
4. Test locally: `cd themes/my-new-theme && npm run dev` with a fixture content collection
5. Submit a PR or commit to your fork — the theme is now available to any simulation on this Ensayo instance

The author guide ships with Phase 9 documentation. The eight initial themes serve as worked examples.

**Theme dependency locking:**

Each theme commits its `package-lock.json`. The generator runs `npm ci` (not `npm install`), which fails fast if the lock file is out of sync. This prevents transitive-dependency drift from breaking yesterday's themes today.

**Pre-vendored node_modules:**

The Tier-1 GHCR image bundles `node_modules/` for every shipped theme so first-run builds succeed without network access. UCs can build any pre-shipped theme offline. Custom themes added later require `npm ci` against the network the first time they are built.

---

## 14. Phased Implementation Roadmap

### Phase 0: Foundation + Zero-Config Demo (Weeks 1–3)

**Deliverable:** Runnable Python package with CLI, config loading, four ported Astro themes, a generated single-company site, and a working Tier-1 Docker image with path-based Caddy fallback.

**Scope — Python:**
- Python package scaffolding (`pyproject.toml`, Click CLI, directory structure)
- YAML config loading and validation (`company.yaml` schema)
- Theme orchestration: read theme.yaml, copy theme package, generate Astro content collections, run `npm ci && npm run build`, capture dist/
- Basic site generation: `ensayo generate --config company.yaml --output ./dist`
- Output directory structure matches the existing company-site pattern

**Scope — Themes (port four WorkReady sites to Astro packages):**
- `portal-clean` — derived from `workready-portal`. Required for any multi-site portal in later phases.
- `directory` — derived from `workready-jobs`. Required for any hub/board view.
- `tech-modern` — derived from `nexuspoint-systems`. First distinctive corporate theme.
- `finance-traditional` — derived from `southern-cross-financial`. Second distinctive corporate theme covering professional services.

Each theme:
- Becomes an Astro package with its own `package.json` and pinned `package-lock.json`
- Declares `theme.yaml` (name, supports, features, content_props)
- Decouples WorkReady-specific content from the visual layer (content arrives via Astro content collections from the simulation YAML)
- Includes a fixture content collection for `npm run dev` standalone development

**Scope — Deployment:**
- **`install.sh` as single source of truth** — works for bare-metal and Dockerfile (zero drift between paths)
- **`docker-compose.yml` and `Dockerfile`** producing a runnable image with Python 3.12, Node 20, Caddy, Ensayo, all four themes with vendored `node_modules`, and a stub-LLM demo simulation pre-loaded
- **Path-based Caddy fallback** for no-DNS local mode (`{$DOMAIN_X:fallback.localhost}` pattern)
- **GHCR image publishing** via GitHub Actions on push to main
- **`instance.env` / `.env` split** with example files
- Built-in keyword chatbot JS (~100 lines, no external deps) shipped as a shared component the themes consume

**Validation:** A new user runs `git clone && docker compose up -d` and reaches a working keyword-chatbot simulation at `http://localhost` within minutes, with no API keys, no DNS, no AnythingLLM, no internet beyond the initial pull. The demo simulation uses one of the four ported themes. This is the zero-config-first-run guarantee from §1.

**Note on duration:** Phase 0 expands from 2 to 3 weeks because porting four WorkReady sites to Astro themes is real work — each is a 1–2 day effort to extract the visual identity, parameterise the content surfaces, and verify against fixture data.

---

### Phase 1: Employees and Chatbot Prompts (Weeks 3–4)

**Deliverable:** Layered prompt generation producing chatbot system prompts.

**Scope:**
- Role archetype library (10 archetypes as YAML)
- Layered prompt builder (archetype → industry → company → individual)
- Generated prompt files (`{slug}-prompt.txt`) per employee
- Keyword-mode chatbot support (`keywords.json` generation)
- Client-side keyword chatbot engine
- AnythingLLM embed integration in generated pages

**Validation:** Generate prompts for 7 employees. Verify keyword mode by generating a TechNova-equivalent site.

---

### Phase 2: Content Library, LLM-Assisted Generation, Remaining Themes (Weeks 5–7)

**Deliverable:** LLM-assisted content creation in the generator, full content library, and the remaining four ported themes.

**Scope — Content:**
- LLM provider abstraction (stub + Ollama + OpenAI-compatible + Anthropic + Gemini)
- `ensayo generate --with-llm` CLI flag using LLM to enrich content
- **Bulk-generation pipeline at simulation creation** (§10.6): generate all backstories, documents, scenario, culture in one pass with token-count estimate, polled progress (spinner UX), partial-failure recovery, and per-item regenerate
- **Job-based generation API**: `POST /api/v1/jobs/bulk-generate` returns a `job_id`; `GET /api/v1/jobs/{job_id}/status` reports progress; same lazy/poll pattern as the rest of the platform — no SSE, no WebSocket
- Token-count estimator (input + output tokens by item type) so the wizard can preview scope before commit
- Per-surface stub responders (§8.7) for content generation in stub mode — skeleton templates that fall back gracefully when no LLM is configured
- Industry template library (6 industries, including software_development)
- Scenario template library (5 scenarios)
- Document template library
- `ensayo list` command

**Scope — Themes (port the remaining four WorkReady sites):**
- `mining-rugged` — from `ironvale-resources`. Heavy industry, resources, manufacturing.
- `nfp-warm` — from `horizon-foundation`. Charity, NFP, social enterprise.
- `government-formal` — from `metro-council-wa`. Local government, public sector.
- `advisory-cool` — from `meridian-advisory`. Consulting, professional services.

After Phase 2, the eight initial themes cover: portal, directory, tech, mining, NFP, finance, government, advisory.

**Validation:** Generate a complete simulation from a minimal `company.yaml`. Generate eight different demo simulations, each using a different theme, to confirm visual diversity.

---

### Phase 3: Simulation API + UC Dashboard MVP (Weeks 7–10)

**Deliverable:** A FastAPI backend serving multi-simulation content management, student auth (shared password), and the UC dashboard.

**Scope:**
- FastAPI application with SQLite backend
- Database schema (simulations, UCs, companies, employees, documents, visibility rules, student access, bookings)
- Per-instance UC accounts with admin/UC roles
- JWT authentication for UCs
- Git working clone management (clone, pull, commit, push) with per-simulation locking
- UC dashboard frontend (single-page HTML/JS) — login, simulation list, configuration wizard (Steps 1–9 from §10.2)
- The lay-person wizard
- Booking service
- Visibility-rule enforcement
- Docker compose deployment with Caddy reverse proxy

**Validation:** Run the full single-company workflow: instance admin creates UC, UC creates simulation via wizard, edits content, deploys to GitHub Pages, students access via shared password.

**MVP cutoff:** End of Phase 3. Single-company simulations, dashboard-driven, GitHub Pages, shared password auth.

---

### Phase 4: AnythingLLM Automation and Booking Integration (Weeks 11–12)

**Deliverable:** Automated AnythingLLM workspace provisioning and booking-gated chatbot access.

**Scope:**
- AnythingLLM setup integrated into the dashboard (workspace creation, prompt upload, RAG document upload, embed widget generation)
- Booking-gated chatbot frontend (`chatbot-booking.js`, `booking-modal.js`, `booking-api.js`)
- Dashboard "Provision chatbots" action
- Booking analytics view

**Validation:** Create a simulation, provision AnythingLLM workspaces, book an appointment as a student, chat with the employee. Verify RAG-grounded responses.

---

### Phase 5: Individual Student Accounts (Weeks 13–14)

**Deliverable:** Individual student authentication and student management.

**Scope:**
- Individual student account registration and login
- CSV whitelist upload
- Password reset via email (SMTP)
- Email-only auth mode
- Student management dashboard (student list, password reset, data export)
- Per-student engagement metrics

**Validation:** Set up a simulation with individual accounts, whitelist 10 students, test full registration/login/reset flow.

---

### Phase 6: Safe Mode and Audience Configuration (Weeks 15–16)

**Deliverable:** Audience-mode selection at simulation creation, with the minors-safe defaults bundle.

**Scope:**
- Audience setting in simulation configuration (adults/minors)
- Defaults bundle implementation (auto-set chatbot mode, auth mode, surface availability)
- Override banner UI in the dashboard
- LLM-assist disable/confirm in minors mode
- Aggregate-only logging in minors mode
- Filtered base library presentation in minors mode (mature archetypes hidden)

**Validation:** Create a `minors`-mode simulation. Verify bundle defaults applied. Test override banner appears for any deviation. Confirm no PII is captured. Use a TechNova-equivalent scenario.

---

### Phase 7: Workflow Engine Spike (Week 17)

**Deliverable:** Validated declarative workflow YAML schema.

**Scope:**
- Implement the workflow engine reading `workflow.yaml`
- Implement at least the internship workflow end-to-end
- Implement at least one additional workflow (medical or financial) end-to-end with stub LLM
- Document any escape hatches needed for non-internship logic
- Decision: continue with declarative workflow OR add Python plugin mechanism

**Validation:** Run a student through both workflows with stub LLM. Verify same surfaces activate at different stages without code changes. Document any limitations encountered.

**Gate:** Phase 8 cannot start until this spike confirms the schema is sufficient. If the spike reveals fundamental limitations, redesign before committing to multi-site implementation.

---

### Phase 8: Multi-Site Simulations (Weeks 18–22)

**Deliverable:** Full multi-site simulation generation and lifecycle management with all six interaction surfaces.

**Scope:**
- `simulation.yaml` format for multi-site configuration
- Multi-site generation (portal + directory + N company subpaths from one config, one repo)
- Configurable workflow engine implementation (validated by Phase 7 spike)
- Interaction surface implementations:
  - **In-app messaging** — dual inbox, lazy delivery, attachments
  - **1-on-1 conversation** — parameterised by `kind`, configurable system prompt, LLM-assessed
  - **Group conversation** — beat arc planning, lazy delivery, `@mention` rescheduling, participation review
  - **Document submission** — upload, LLM review, lazy-gated feedback, progressive task reveal
  - **Booking** — tiered availability, business hours, slot generation, random rescheduling, ICS
  - **Assessment** — structured LLM evaluation reusable across surfaces
- Student portal (sign-in, dashboard, dual inbox, conversation UI, task management, group chat view, journey report)
- Directory/board site (parameterised hub view, filtering, blocking)
- Workflow templates: internship, medical_network, financial_markets
- **Optional primer support:** ship one Ink-based primer template (`internship-primer.ink`, derived from `workready-primer/`); generator wires it into the multi-site build when the UC opts in via `simulation.yaml`; vendored inkjs runtime; primer build pipeline (`ensayo primer build`)
- **External tool export endpoints:** application, conversation, group-chat, journey, cohort exports with stable `schema_version` JSON contract

**Validation:** Generate a multi-site internship simulation from configuration. Run a student through the full lifecycle, including the optional primer. Verify export endpoints return stable JSON. Generate a medical network simulation with a different workflow and verify the same interaction surfaces activate at different stages without schema changes.

---

### Phase 9: Polish and Documentation (Weeks 23–24)

**Deliverable:** Production-ready platform with documentation.

**Scope:**
- UI polish for dashboard and generated sites
- Documentation:
  - Getting Started guide (for UCs)
  - Configuration Reference (`company.yaml` and `simulation.yaml` schema)
  - Deployment Guide (Docker, GitHub Pages, AnythingLLM setup, custom domains)
  - Theme Authoring Guide
  - Archetype Authoring Guide
  - Safe Mode Operational Guide (for school deployments)
- Theme gallery (10–12 themes)
- Accessibility audit (WCAG 2.1 AA)
- Security review

**Validation:** Documentation walkthrough: a new UC creates their first simulation following only the Getting Started guide.

---

### Roadmap Summary

```
Week  1–3  ┃ Phase 0: Foundation + 4 ported Astro themes + zero-config demo
Week  4–5  ┃ Phase 1: Employees and chatbot prompts
Week  6–8  ┃ Phase 2: Content library + LLM-assisted generation + remaining 4 themes
Week  9–12 ┃ Phase 3: Simulation API + UC dashboard MVP   ← MVP cutoff
Week 13–14 ┃ Phase 4: AnythingLLM automation + booking
Week 15–16 ┃ Phase 5: Individual student accounts
Week 17–18 ┃ Phase 6: Safe mode and audience configuration
Week  19   ┃ Phase 7: Workflow engine spike   ← Gate before Phase 8
Week 20–24 ┃ Phase 8: Multi-site simulations
Week 25–26 ┃ Phase 9: Polish and documentation
```

**Minimum viable product (MVP):** Phases 0–3. A UC can create a single-company simulation, configure it via the dashboard, deploy to GitHub Pages, and have students access it with a shared password.

**Full product:** Phases 0–9. Production-ready with multi-site, individual accounts, AnythingLLM, safe mode, and complete documentation.

---

## 15. Open Questions and Risks

### 15.1 Decisions Made

| Question | Decision |
|----------|----------|
| Generator standalone CLI or API endpoint? | Both — Python library imported by API; CLI wrapper for power users and CI/CD |
| Simulation API monolith or microservices? | Modular monolith (single FastAPI app with internal routers) |
| Relationship to WorkReady? | Greenfield. WorkReady is reference inspiration only; no migration |
| Relationship to CloudCore / Pinnacle / TechNova? | Greenfield. These are reference inspiration only; no migration |
| YAML / JSON / TOML for configuration? | YAML for human-edited config; JSON for machine outputs; TOML only for Python packaging |
| Dashboard frontend framework? | Vanilla HTML/JS for MVP; revisit if dashboard grows complex |
| Workflow engine declarative or procedural? | Declarative; validated by Phase 7 spike before multi-site implementation |
| Hub views: separate site or portal-internal? | Portal-internal at subpath (one repo per simulation) |
| Static vs self-hosted? | One model: VPS + GitHub Pages. No purely-static deployment |
| Per-site custom domains? | Future work. MVP uses subpaths of one custom domain |
| Base library versioning? | Frozen at simulation creation. No auto-pull |
| Multi-tenant or self-host? | Open self-host. Anyone can deploy their own instance |
| Multi-UC content edits? | Owner edits shared content; co-coordinators hide via visibility rules; clone-to-fork for divergence |
| Where does the generator run? | On the VPS, called by the dashboard. No GitHub Actions in MVP |
| Audience modes? | Two: `adults` (default) and `minors` (safe-mode bundle, see §7) |
| Install script for bare-metal vs Docker? | Single `install.sh` is the source of truth. Dockerfile runs the same script during build. Pattern adopted from workready-deploy. |
| Pre-built Docker image? | Yes — published to GHCR on every push to main. Ships with stub LLM, keyword chatbots, and pre-built themes (vendored `node_modules`) so first-run requires no API keys and no internet beyond the initial pull. |
| First-run experience? | Zero-config: `docker compose up -d` works without DNS, without API keys, without AnythingLLM. Path-based Caddy routing (`/sims/{slug}/`) and stub LLM make this a deployment guarantee, not a "lite mode." |
| Config file structure? | Two files: `instance.env` (domain, admin email, base URL — reviewable) and `.env` (LLM keys, GitHub token, AnythingLLM key — secret). |
| CORS handling? | Caddy injects CORS headers based on configured custom domain(s). API stays generic. |
| Theme rendering? | Astro packages, not Jinja2. Each theme has its own templates, components, and scoped CSS. The eight initial themes are derived from the existing WorkReady sites (`portal-clean`, `directory`, `tech-modern`, `mining-rugged`, `nfp-warm`, `finance-traditional`, `government-formal`, `advisory-cool`). |
| Node.js role? | Build-time only on the VPS. Deployed sites are pure static HTML on GitHub Pages — no Node at deploy or runtime. |
| Adding a new theme? | Author a new Astro package under `themes/`, declare `theme.yaml`, commit `package-lock.json`. The first build of a custom theme requires `npm ci` against the network; pre-shipped themes have vendored `node_modules`. |
| Notification delivery? | Single `notify()` adapter (pattern from workready-api). MVP: in-app inbox only. Email, Telegram, Teams plug in as additional channels later via `register_channel()`. |
| Persona prompt storage? | `.txt` files at `<simulation>/content/employees/{slug}-prompt.txt` in the repo. API reads at runtime via `SITES_DIR`. Editing a persona = editing a repo file (which the dashboard pushes), not a DB row. |
| Database migrations? | Idempotent on-startup pattern from workready-api: `_migrate()` runs on every API start, adds columns `IF NOT EXISTS`. Safe to re-run. No separate migration tool. |
| LLM stub mode? | Per-surface stubs, not one generic stub. Each conversation surface has its own tone-appropriate canned response generator. Stub mode is a Phase-0 deliverable, not an afterthought. |
| Configuration layering? | Two layers: instance env vars (deployer-set defaults for timing, blocking, max-cycles) + per-simulation YAML (UC-set content + tuning overrides). Resolution: per-simulation > instance env > built-in default. |
| External tool integration? | Optional standardised export endpoints. Stable JSON contract with `schema_version`. Any external tool (Talk Buddy, Career Compass, gradebook) consumes via `/api/v1/export/*`. Generic, not WorkReady-specific. |
| Interactive primer? | Optional per-simulation, recommended for advanced multi-site sims. Ink-based static interactive fiction at `/primer/` subpath. Templates per workflow type ship with the platform. Phase 8 deliverable. |
| LLM bulk-generation default at creation? | **ON** for `audience: adults` when an LLM provider is configured (Ollama / Anthropic / OpenRouter / Gemini / OpenAI). **OFF** for `audience: minors` and when only stub mode is available. The wizard shows a token-count estimate (UC looks up provider pricing themselves) and uses a polling-based job pattern (spinner + 2s poll) for progress. Supports partial-failure recovery + per-item regenerate. See §10.6. |
| Save vs Publish? | Two-state edit model. **Save** writes YAML to working clone (per-simulation lock, low friction). **Publish** commits + pushes to GitHub (deliberate, students see changes within ~1 minute). Optional Auto-publish toggle per-simulation. See §10.1. |
| Student data deletion? | **Soft delete** with PII redaction. `student_access.deleted_at` set; `email` + `name` nulled; transcripts/submissions/messages anonymised; AnythingLLM history cleared. No reactivation — returning student is a new identity. Hard-delete via `ensayo admin purge-student` for escalated cases. Email reuse after `STUDENT_EMAIL_RETENTION_DAYS` (default 30). See §6.7. |
| Identity vs email? | `student_access.id` (UUID) is the canonical primary key; `email` is a mutable identifier. Foreign keys never reference email. Email changes do not affect history or analytics. |
| Observability? | Structured JSON logs to stderr + rotated file (`/var/ensayo/logs/`). Logs API requests, generation events, audit events, errors, notification dispatch, theme override warnings. Minors mode logs aggregate only. **No log viewer / dashboard / alerting in the platform** — future work is a separate observability tool consuming the JSON stream. See §3.6. |
| Theme compatibility checks? | **Advisory, not blocking.** Wizard recommends compatible themes; UC can override; override is logged. Pattern of overrides signals when to extend a theme's `supports:` declaration in the next platform release. See §13.7. |

### 15.2 Open Decisions

These remain to be decided during implementation:

1. **GitHub repo creation:** When a UC creates a new simulation, does the dashboard create the repo via the GitHub API, or does the UC create it manually and provide the URL? Recommendation: dashboard creates it via API for the lay-person path; manual URL is supported for power users with existing repos.

2. **Backup strategy:** SQLite backup cadence and retention. Probably hourly snapshot to local disk + daily upload to S3-compatible storage, configurable per instance.

3. **Multi-instance federation:** Can two Ensayo instances share simulations? Probably not in MVP — keep instances independent. Worth revisiting if institutions want to share simulations across departments running separate instances.

4. **Simulation export/import format:** A simulation is just a git repo, so "export" is `git clone`. But we may want a `.ensayo` archive format that bundles the YAML + DB cache + AnythingLLM workspace specs for offline transfer.

5. **Backup and disaster recovery in detail.** §15.2 item 2 covers SQLite backup cadence; the broader scope (AnythingLLM workspace recovery, what happens if a simulation repo is accidentally deleted on GitHub, restoring an instance from scratch on a new VPS, restoring a single simulation to a point-in-time before a UC's bad edit) is undecided. Resolve in Phase 9 (Polish + Documentation).

### 15.3 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **LLM-generated content quality is insufficient** | Medium | Medium | LLM is always optional. Generated content is a starting draft, not the final product. Instructor edits are expected. |
| **AnythingLLM API changes break workspace automation** | Medium | Low | Pin AnythingLLM version. The setup is isolated and can be updated independently. Fallback to non-RAG mode. |
| **SQLite performance limits under concurrent student load** | Low | Medium | WAL mode for concurrent reads. Realistic load is tens, not thousands. PostgreSQL migration is straightforward if needed. |
| **Cross-origin issues between static sites and the API** | Medium | Low | API configures CORS per simulation. AnythingLLM embeds are designed for cross-origin. |
| **Prompt injection in student chatbot conversations** | High | Low | Chatbot personas are simulation context, not security context. "Breaking character" is annoying, not dangerous. AnythingLLM has built-in prompt safety. System prompts include "stay in character" instructions. Audience mode disables LLM chatbots for minors. |
| **Student data privacy compliance varies by institution** | High | High | The platform provides options (`minors` mode, shared password = no PII). Deployment documentation includes a privacy checklist. Individual account mode requires institutional clearance. |
| **Theme CSS Zen Garden approach proves too limiting** | Low | Medium | Theme CSS has full control. Custom page templates can be added per simulation. Base HTML uses semantic classes that are stable across themes. |
| **Declarative workflow engine too rigid for non-internship domains** | Medium | Medium | Phase 7 spike validates this before Phase 8 commits. Add escape-hatch Python callbacks if needed. |
| **Dashboard git push fails (network, auth, GitHub down)** | Medium | Medium | Dashboard retries with exponential backoff. UC sees a clear error. Working clone is left in a consistent state for manual recovery. |
| **VPS disk fills with working clones over time** | Low | Low | Working clones are pruned for archived simulations. Disk usage monitored. |
| **Mid-semester platform update breaks running simulations** | Medium | High | Simulations are frozen against base library at creation. Platform updates affect new simulations only. Database migrations are versioned and reversible. UCs are notified before any operation that requires re-generation. |
| **Override banner fatigue in minors mode** | Low | Low | Banners are persistent but specific. UCs who consistently override defaults probably should be using `adults` mode. |
| **npm transitive dependency drift breaks themes** | Medium | Medium | Each theme commits `package-lock.json`; generator uses `npm ci` (fail-fast on lock-file mismatch). GHCR image vendors `node_modules` for shipped themes. Custom themes that don't lock are the user's risk. |
| **Astro major-version upgrades break shipped themes** | Low | Medium | Themes pin their Astro version. Upgrades are a per-theme PR with regression testing against fixture content collections. Existing simulations are unaffected (their dist/ is already built and committed). |

### 15.4 Spikes and Prototypes

**Inside Phase 0 (before committing the four ports):**

0. **Astro theme port-of-one spike:** Take one WorkReady site (recommend `nexuspoint-systems` → `tech-modern`) and port it end-to-end as an Astro theme package. Validate: (a) the visual output matches the original, (b) content collections cleanly accept arbitrary `company.yaml` data, (c) `npm ci && npm run build` produces deployable static output, (d) build time per simulation is under 30 seconds. If the port reveals fundamental issues (e.g. WorkReady's markup uses patterns Astro components can't reproduce cleanly), redesign before porting the other seven sites.

**Before Phase 3 (Simulation API):**

1. **AnythingLLM API version compatibility spike:** Verify workspace creation, prompt upload, and embed widget APIs against current AnythingLLM version. Document any breaking changes from prior reference implementations.

2. **Multi-simulation SQLite spike:** Prototype the schema with 10 concurrent simulations. Verify lock contention is acceptable.

3. **Git push-from-dashboard spike:** Prototype the working-clone management — pull, edit, commit, push from inside a FastAPI request handler. Measure latency for typical edits. Verify error handling for push failures.

4. **LLM-assisted content quality spike:** Generate 5 employee backstories using the layered prompt builder with 3 different LLM providers. Evaluate quality and consistency. Determine whether LLM-generated content needs a mandatory human review step.

**Before Phase 6 (Safe Mode):**

5. **Audience defaults consistency spike:** Verify that the minors-safe defaults bundle propagates correctly through the full stack (UI, API, generator, AnythingLLM provisioning). Look for places where a single override could leak through.

**Before Phase 8 (Multi-Site):**

6. **Workflow engine validation spike** (Phase 7 itself): As described above. Implementing two distinct workflows (internship + healthcare or financial) with the declarative YAML schema, end-to-end with stub LLM. Decision gate before committing to multi-site implementation.

7. **Subpath multi-site routing spike:** Verify GitHub Pages serves a multi-site simulation correctly with relative URLs for all assets. Test edge cases (deep links, theme CSS scoped to subpaths, AnythingLLM embeds across subpaths).

### 15.5 What Ensayo Deliberately Doesn't Include

Pattern adopted from workready-api's "Things that look like they exist but don't" section. Setting absences explicitly avoids contributors building toward features that aren't planned.

- **No background workers, cron, or job queues.** Every "happens later" feature uses lazy delivery: persist a row with `deliver_at`, filter on read. Do not reach for Celery, RQ, APScheduler, or systemd timers. This is deliberate — see §11/§12 lazy-delivery pattern.
- **No multi-process API.** One uvicorn process. SQLite WAL gives us enough concurrency for the assumed load (tens of concurrent students). Horizontal scaling is not designed for and would require rearchitecting around PostgreSQL.
- **No real-time / WebSocket / SSE.** Portals poll. Lazy delivery + ~3s poll interval is the chat experience. No need for push.
- **No team / multi-student tasks.** Each student goes through the simulation alone. Group conversations involve one student plus AI participants, not multiple students.
- **No video / voice.** Every conversation is typed. No WebRTC, no media transcoding.
- **No aggregate grade in the journey report.** Journey reports show what happened; lecturers grade. Auto-grading would create accountability problems disproportionate to its educational value.
- **No native mobile apps.** Static sites are responsive. Mobile browsers are the supported mobile experience.
- **No SaaS hosting.** Ensayo is open self-host. We are not running a hosted service or marketplace.
- **No password recovery via security questions.** SMTP-based reset only (when configured); admin reset otherwise.
- **No social features.** No student profiles visible to other students, no comments, no reactions, no leaderboards.
- **No content moderation pipeline for student inputs.** Student free-text inputs (chat messages, task submissions) are not moderated by the platform. Moderation responsibility lies with the UC (which is why minors mode disables most free-input surfaces by default).
- **No automatic UI translation.** Sites are generated in the language the UC writes them in. i18n is not on the roadmap.
- **No PR / approval workflow inside the dashboard.** Co-coordinators hide content via visibility rules or clone the simulation. They don't propose edits to shared content for owner approval; that's a future possibility but not in scope.

If a contributor or stakeholder requests one of the above, the answer is "out of scope" — not because it would be impossible, but because the platform's value comes from doing the educational pipeline well, not from being a general-purpose simulation framework.

---

*End of specification.*
