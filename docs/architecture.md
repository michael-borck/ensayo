# Ensayo Architecture Overview

This is the short, navigable map. The authoritative design is
[`SPECIFICATION.md`](SPECIFICATION.md) (v2); the *why* behind each major choice is
in [`adr/`](adr/). Domain vocabulary is in [`../CONTEXT.md`](../CONTEXT.md).

## The one-paragraph version

Ensayo is a **generator platform**: a Unit Coordinator describes a fictional
company in `company.yaml`, and Ensayo produces a complete, deployable simulation
website. The generator and all dynamic features run as a single service on a VPS
(packaged as a Docker image); the **student-facing site is pushed to GitHub Pages
as pure static files**, and the student's browser calls back to the VPS only for
dynamic features (auth, booking, LLM chat). See [ADR-0001](adr/0001-hosting-static-pages-dynamic-api.md).

## Full design (Phase 3+)

```
   ┌────────────────────── VPS (Docker) ──────────────────────┐
   │  Ensayo Services (one FastAPI app — ADR-0002)             │
   │   • UC dashboard (/admin/)   • generator (Python library) │
   │   • auth / booking / chat proxy / messaging / workflow    │
   │   • SQLite (runtime + content cache — ADR-0005)           │
   │   • git working clones (one per simulation)               │
   │   • Caddy: TLS, path routing, CORS (ADR-0003)             │
   └───────────────┬───────────────────────────────────────────┘
                   │ generate → commit → push
                   ▼
            ┌──────────────┐   loads static site
            │ GitHub Pages │ ◄──────────────────────  student browser
            │  (per sim)   │ ──────────────────────►  (JS calls /api/v1/* on VPS)
            └──────────────┘
```

## What exists today (Phase 0)

Only the **generator + theme pipeline + zero-config Docker demo**. There is no
FastAPI service, dashboard, or GitHub-push yet — so in Phase 0 the container both
generates *and* serves the demo via Caddy. That serving role moves to GitHub Pages
once Phase 3 adds the service and push flow.

```
company.yaml ──► ensayo (Python) ──► content/  (canonical: personas, prompts, docs)
                       │
                       └─► Astro theme build ──► dist/ ──► (Phase 0) served by Caddy
                                                          (Phase 3+) pushed to GitHub Pages
```

### Component map (current code)

| Path | Role |
|------|------|
| `src/ensayo/cli.py` | `ensayo` commands (generate / validate / list / init) |
| `src/ensayo/config.py` + `models.py` | Load & validate `company.yaml` (Pydantic) |
| `src/ensayo/prompts.py` | Persona prompt, profile, and keyword-chatbot builders |
| `src/ensayo/content.py` | Write canonical `content/` + theme `src/data/` |
| `src/ensayo/generator.py` | Orchestrate: theme copy → inject → Astro build → capture `dist/` |
| `src/ensayo/themes.py` | Theme discovery + `theme.yaml` manifests |
| `src/ensayo/shared/keyword-chatbot.js` | Client-side deterministic chatbot |
| `themes/<name>/` | Astro theme packages (ADR-0004) |
| `install.sh`, `Dockerfile`, `docker-compose.yml`, `deploy/` | Deployment (ADR-0003) |

## Phase roadmap (SPECIFICATION.md §14)

```
Phase 0  Foundation                       ✅ done
Phase 1  Prompts + archetype library      ✅ done
Phase 2  LLM-assisted gen (+ more themes) ✅ (6 company themes; portal+directory in P8)
Phase 3  FastAPI + UC dashboard           ✅ MVP reached (guided-wizard UI polish pending)
Phase 4  AnythingLLM + booking            ✅ provisioning + booking-gated chat + booking analytics
Phase 5  Individual student accounts      ✅ accounts/email-only/whitelist/reset/mgmt
Phase 6  Safe mode / audience config      ✅ bundle + override banners + mature filter + privacy notice
Phase 7  Workflow engine spike (gate)     ✅ GATE PASSED — declarative engine (ADR-0008)
Phase 8  Multi-site simulations           ◑ generation done (portal + companies, 1 repo); runtime surfaces + portal/directory themes pending
Phase 9  Polish + documentation
```
