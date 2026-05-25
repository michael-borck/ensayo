# Changelog

All notable changes to Ensayo. The platform was built phase-by-phase following the
roadmap in [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md) §14.

## 0.1.0 — initial build (Phases 0–9)

### Phase 0 — Foundation
- `ensayo` CLI (`generate` / `validate` / `list` / `init`), `company.yaml` schema
  (Pydantic), content generation, the `tech-modern` Astro theme, a client-side
  keyword chatbot, and a zero-config Docker image (`install.sh` + Caddy).

### Phase 1 — Prompts & archetypes
- Role-archetype library (10 + `staff`), industry library, and a layered prompt
  builder (archetype → industry → company → individual); per-employee
  `keywords.json`; AnythingLLM embed hook.

### Phase 2 — LLM-assisted generation
- LLM provider abstraction (stub/ollama/lmstudio/openai/openrouter/gemini/anthropic),
  bulk content generation with token estimate + partial-failure recovery, per-surface
  stubs, and the industry/scenario/document template libraries.

### Phase 3 — FastAPI + dashboard (MVP)
- FastAPI service, SQLite with idempotent migrations, UC accounts + JWT, git
  working clones, the lecturer dashboard, Save-vs-Publish with **GitHub Pages
  publish**, per-simulation locking, shared-password student auth, booking, and
  server-enforced visibility rules.

### Phase 4 — AnythingLLM + booking
- AnythingLLM workspace provisioning (dry-run when unconfigured), booking-gated
  chatbots, cross-origin API base, and booking analytics.

### Phase 5 — Individual student accounts
- Auth modes (shared / individual / email-only), CSV whitelist, password reset
  (SMTP or returned code), student management, soft-delete with PII redaction, CSV
  export, and per-student metrics.

### Phase 6 — Safe Mode
- The minors-safe defaults bundle with acknowledged overrides + persistent banner,
  mature-archetype filtering, a per-page privacy notice, and aggregate-only audit
  logging.

### Phase 7 — Workflow engine (gate)
- A declarative `workflow.yaml` engine validated across two domains (internship,
  medical) — the decision gate before multi-site (ADR-0008).

### Phase 8 — Multi-site simulations
- `simulation.yaml` (portal + N companies, one repo, subpaths); the workflow wired
  to per-student application state with an in-app inbox (lazy delivery); the six
  interaction surfaces (messaging, booking, 1-on-1 conversation, group chat,
  document submission, assessment); the student portal; the `portal-clean` and
  `directory` themes; and versioned export endpoints.

### Phase 9 — Polish & documentation
- Full documentation set (getting-started, configuration reference, deployment,
  theme & archetype authoring, safe-mode ops), a security review, accessibility
  pass, an `ensayo gallery` command, and a theme gallery.

8 Astro themes; 100+ tests.
