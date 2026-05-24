# Ensayo — Domain Context

The shared vocabulary for this codebase. Use these terms precisely; they map
directly onto code, config keys, and the data model. Authoritative detail lives in
[`docs/SPECIFICATION.md`](docs/SPECIFICATION.md); architectural reasoning in
[`docs/adr/`](docs/adr/).

## Core nouns

- **Ensayo** — the generator *platform* (this repo). Not a simulation; the tool
  that produces simulations.
- **Simulation** — one teaching scenario: a fictional organisation (or network of
  them) rendered as a website. The top-level unit of content. One git repo each.
  Two kinds: **single-company** and **multi-site**.
- **Company (site)** — a fictional organisation within a simulation. Single-company
  sims have exactly one; multi-site sims have many (served at subpaths).
- **Employee** — a virtual person in a company. Has a **persona**.
- **Persona / prompt** — an employee's character, expressed as a system prompt at
  `content/employees/<slug>-prompt.txt` (canonical; the API reads it at runtime).
- **Document** — any content file in a simulation (policy, support doc, dataset,
  transcript, etc.).
- **Scenario** — the narrative tension a simulation is built around (e.g. a breach,
  a growth pivot). Gives the sim coherence; every employee has a perspective on it.

## People (three identity tiers)

- **Instance admin** — deploys and operates an Ensayo instance (the VPS). Creates
  UC accounts, configures LLM providers.
- **Unit Coordinator (UC) / Lecturer** — creates and owns simulations through the
  dashboard; manages content and students. Can be a **co-coordinator** on another
  UC's simulation (scoped to a `unit_code`, can hide content via visibility rules
  but not edit shared canonical content).
- **Student** — navigates a simulation site; chats, books, reads, submits. Three
  auth modes: **shared password**, **individual account**, **email-only**.

## Generation pipeline

- **Generator** — the Python engine (`ensayo.generator`) that turns `company.yaml`
  into a site. Also the `ensayo` CLI.
- **`company.yaml` / `simulation.yaml`** — the human-authored config; **canonical
  for content** (single-company vs multi-site).
- **content/** — generated canonical files (employee `.md` profiles, `-prompt.txt`
  personas, `docs/*.md`). Git-canonical.
- **Theme** — a full Astro package (`themes/<name>/`) defining the visual identity.
  Declares a `theme.yaml`. Consumes content via Astro **content collections**.
- **dist/** — the built static site (HTML/CSS/JS). Derived; deployed to GitHub
  Pages (Phase 3+).
- **base path** — the URL prefix a site is built for (`/` at a domain root, or
  `/sims/<slug>/` for path routing / multi-site subpaths).
- **archetype** — a reusable role template (e.g. `founder_ceo`, `operations_manager`)
  that seeds an employee's persona. The **layered prompt builder** composes
  archetype → industry → company → individual (Phase 1).

## Chatbots

- **Keyword mode** — deterministic, client-side chatbot (no LLM, no network). The
  zero-config default and the minors-safe default. Data in each employee's
  `keywords` payload; engine is `shared/keyword-chatbot.js`.
- **LLM mode** — chatbot backed by an LLM (via the VPS LLM proxy or AnythingLLM).
- **hybrid** — both.

## Safety & audience

- **Audience** — `adults` (full features) or `minors` (the **minors-safe bundle**:
  keyword chatbots only, shared-password auth, no messaging/inbox/group chat,
  aggregate-only logging, single-company only). A *bundle of defaults*, not one
  flag; overriding any default raises a persistent banner.
- **Safe mode** — informal name for the minors audience configuration.

## Runtime concepts (Phase 3+)

- **Working clone** — the VPS's local git checkout of a simulation, where the
  dashboard writes YAML, regenerates, commits, and pushes.
- **SQLite** — canonical for **runtime state** (bookings, students, transcripts,
  tasks) and a rebuildable **cache** of content metadata.
- **Visibility rule** — server-enforced, optionally `unit_code`-scoped, time- or
  condition-based show/hide of content.
- **Lazy delivery** — "happens later" implemented as a `deliver_at` row filtered on
  read; **no background workers** (see ADR-0007).
- **Interaction surfaces** (multi-site) — messaging, 1-on-1 conversation, group
  chat, document submission, booking, assessment. Composable building blocks the
  workflow engine activates per stage.

## Reference projects (inspiration only — no migration)

- **CloudCore** — the single-company pattern (deep personas, doc ecosystem).
- **WorkReady** — the multi-site pattern (portal + job board + N companies + API).
- **TechNova** — the safe-mode pattern (keyword chatbots for school students).
- **nexuspoint-systems** — source for the `tech-modern` theme and the bundled demo.
