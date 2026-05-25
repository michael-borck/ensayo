# Ensayo

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.12%2B-3776ab)
![tests](https://img.shields.io/badge/tests-105%20passing-brightgreen)
![status](https://img.shields.io/badge/status-v0.1.0-success)
![stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20Astro-111)

Configuration-driven generator for **LLM-assisted workplace teaching simulations**.

A *simulation* is a fictional organisation rendered as a website where students
interact with virtual employees (chatbots), read internal documents, and complete
scenario-driven tasks — in a safe, controlled environment. A lecturer describes
the company in `company.yaml` (or, later, through a dashboard) and Ensayo produces
a complete, deployable static site.

This repository is the platform itself — the generator that *produces*
simulations, not a single simulation.

## Documentation

**Guides** (in [`docs/guides/`](docs/guides/)):
- [Getting Started](docs/guides/getting-started.md) — UC walkthrough, nothing → running sim.
- [Configuration Reference](docs/guides/configuration-reference.md) — every `company.yaml` / `simulation.yaml` field.
- [Deployment](docs/guides/deployment.md) — Docker, GitHub Pages, AnythingLLM, custom domains.
- [Theme Authoring](docs/guides/theme-authoring.md) · [Archetype Authoring](docs/guides/archetype-authoring.md) · [Safe Mode](docs/guides/safe-mode.md).

**Design & reference:**
- [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md) — the canonical (v2) design.
- [`docs/architecture.md`](docs/architecture.md) — navigable overview · [`docs/adr/`](docs/adr/) — decision records.
- [`docs/acceptance-testing.md`](docs/acceptance-testing.md) — manual UAT walkthrough (user stories).
- [`docs/security-review.md`](docs/security-review.md) · [`docs/accessibility.md`](docs/accessibility.md) · [`CHANGELOG.md`](CHANGELOG.md) · [`CONTEXT.md`](CONTEXT.md).

> **Status: all 9 phases complete (v0.1.0).** The `ensayo` CLI + generator, 8 Astro
> themes, LLM-assisted content generation, the FastAPI service + lecturer dashboard,
> GitHub Pages publishing, AnythingLLM chatbots, student accounts, safe mode, the
> declarative workflow engine, and full multi-site simulations (portal + companies +
> six interaction surfaces + student portal + exports) are all built and tested. See
> the [CHANGELOG](CHANGELOG.md) and the roadmap in [`docs/architecture.md`](docs/architecture.md).

## Architecture (current)

```
company.yaml ──► ensayo (Python) ──► content/  (canonical: personas, prompts, docs)
                       │
                       └─► Astro theme build ──► dist/  (static site for GitHub Pages)
```

- **Python** orchestrates: config validation, content generation, theme build.
- **Astro themes** are full packages (`themes/<name>/`) with their own templates,
  components and scoped CSS. Node is a *build-time only* dependency; the deployed
  site is pure static HTML/CSS/JS.
- **Keyword chatbots** run entirely client-side (no LLM, no network) — the
  zero-config default and the minors-safe option.

## Requirements

- Python 3.12+ (and [uv](https://docs.astral.sh/uv/) recommended)
- Node 20+ and npm (only needed to build a theme; `--no-build` skips it)

## Quick start

```bash
# 1. Validate a config
uv run ensayo validate -c examples/nexuspoint/company.yaml

# 2. See available themes
uv run ensayo list

# 3. Generate content only (no Node needed)
uv run ensayo generate -c examples/nexuspoint/company.yaml -o ./out --no-build

# 4. Generate the full static site (runs the Astro build)
uv run ensayo generate -c examples/nexuspoint/company.yaml -o ./out

# 5. Preview it
python3 -m http.server -d ./out/dist 8000   # → http://localhost:8000
```

Scaffold a new simulation from a template:

```bash
uv run ensayo init -o my-company.yaml --name "Acme Corp"
```

## LLM-assisted generation

Give a sparse config (names, roles, archetypes, a scenario *type*) and let the
engine write the rest — backstories, opinions, perspectives, the scenario
narrative, and document bodies:

```bash
# Preview what would be generated + a token estimate (no generation):
uv run ensayo enrich -c examples/sparse/company.yaml --estimate-only

# Generate content + build, in one step:
uv run ensayo generate -c examples/sparse/company.yaml -o ./out --with-llm
```

The provider is chosen from `LLM_PROVIDER` / `LLM_MODEL` / `*_API_KEY` (or a per-sim
`llm:` config), falling back to **stub** — which produces grounded draft skeletons
with no keys and no network. Supported: `stub`, `ollama`, `lmstudio`, `openai`,
`openrouter`, `gemini`, `anthropic`. `ensayo enrich -o enriched.yaml` writes the
filled-in YAML back out for review.

## Dashboard & API (Phase 3)

Run the FastAPI service + lecturer dashboard:

```bash
# 1. Create an instance-admin account
uv run ensayo admin create-uc --email you@uni.edu --admin

# 2. Start the server
uv run ensayo serve                       # → http://127.0.0.1:8000/admin/
```

A Unit Coordinator logs in, creates a simulation (paste a `company.yaml`, optional
shared password, optional LLM generation), **edits** it (Save), and **publishes** it
to GitHub Pages. The server runs the generator into a per-simulation git working
clone (with locking), serves the site locally at `/sims/<slug>/`, and on publish
pushes content to `main` and the built site to the `gh-pages` branch. Students
authenticate with the shared password and can **book appointments**; **visibility
rules** gate content server-side. Configuration: `ENSAYO_DB`, `WORKING_CLONES_DIR`,
`JWT_SECRET`, `GITHUB_TOKEN` (for publish).

> **Status (MVP reached).** Phase 3 delivers: UC/JWT auth, simulation
> create/list/edit(Save)/regenerate, **Save-vs-Publish** with GitHub Pages publish,
> per-simulation locking, shared-password student auth, **booking**, server-enforced
> **visibility rules**, and the lecturer dashboard. Remaining polish: a guided
> multi-step wizard UI (today it's a single YAML form).

### Safe Mode / audience (Phase 6)

Each simulation has an audience: `adults` or `minors`. `minors` is a **bundle of
safe defaults** (spec §7), not one flag — keyword chatbots only, shared-password
auth (no PII), LLM-assist off, single-company, plus a privacy notice on every page
and aggregate-only audit logging. A UC may deviate, but only by acknowledging the
override in `audience_overrides:`; the dashboard then shows a persistent banner
listing the non-default settings, and `GET /api/v1/simulations/{id}/audience`
reports whether the simulation is still minors-safe. Archetypes flagged `mature`
are filtered out of minors simulations.

### Student accounts (Phase 5)

Each simulation picks an auth mode: **shared password**, **individual accounts**
(email + password), or **email-only**. With individual/email-only modes students
register/sign in at `/api/v1/sims/<slug>/students/...`; optionally restrict sign-up
to a **CSV whitelist**. Password reset is by emailed code (SMTP via `SMTP_HOST`…) or,
if SMTP isn't configured, the code is returned for the UC to relay (or the UC resets
manually). The dashboard's **Students** panel lists the roster + per-student metrics,
uploads the whitelist, resets/soft-deletes students (PII-redacting, spec §6.7), and
exports a CSV. Minors-audience simulations are forced to shared password (no PII).

### LLM chatbots & booking-gated chat (Phase 4)

Click **Provision chatbots** to create an AnythingLLM workspace per employee
(system prompt from the persona, documents uploaded for RAG, embed widget created);
the embed ids are written back into the config and the site regenerated. Without an
AnythingLLM instance (`ANYTHINGLLM_URL` / `ANYTHINGLLM_API_KEY`) it runs in
**dry-run** mode so the flow is demonstrable.

Set `platform.chatbot_requires_booking: true` (with `booking_enabled`) to **gate an
employee's chat behind a booking** — students book an appointment and the chat
unlocks once it begins. Sites on GitHub Pages reach the VPS API via
`api_base_url` in the config (empty = same origin). The dashboard's **Bookings**
button shows bookings per simulation.

## Multi-site simulations (Phase 8)

A `simulation.yaml` with a `companies:` list is a **multi-site** simulation: a
portal coordinating several company sites in **one repo**, each at a subpath
(`/<company-slug>/`) with its own theme. `ensayo generate` auto-detects it and
builds the `portal-clean` hub at the root, the `directory` job board at `/jobs/`,
and each company site at its subpath:

```bash
uv run ensayo generate -c examples/workready-mini/simulation.yaml -o ./out
# → out/dist/index.html (portal) + /jobs/ (board) + /<company>/… per company
```

Multi-site is single-repo by design (ADR-0001) and unavailable for `minors`
audiences (spec §7.5). The student runtime — a declarative **workflow** drives each
student's application through stages, with six interaction surfaces (messaging,
booking, 1-on-1 conversation, group chat, document submission, assessment), an
in-app inbox (lazy delivery), the student portal at `/portal/`, and versioned
**export endpoints** for external tools — is all wired to the VPS API.

## Output layout

`ensayo generate` produces a directory shaped like a simulation repo:

```
out/
├── company.yaml                 # copy of the input config
├── content/
│   ├── employees/
│   │   ├── <slug>.md            # persona profile (frontmatter + backstory)
│   │   └── <slug>-prompt.txt    # canonical chatbot system prompt
│   └── docs/<slug>.md           # documents
└── dist/                        # built static site (deploy to GitHub Pages)
```

## Themes

| Theme | For | Source (reference) |
|-------|-----|--------------------|
| `tech-modern` | Technology / SaaS companies | nexuspoint-systems |
| `finance-traditional` | Finance & professional services | southern-cross-financial |
| `mining-rugged` | Mining, resources & heavy industry | ironvale-resources |
| `nfp-warm` | Charities, NFPs & social enterprise | horizon-foundation |
| `government-formal` | Government & public sector | metro-council-wa |
| `advisory-cool` | Consulting & advisory | meridian-advisory |
| `portal-clean` | Multi-site student portal / hub | workready-portal |
| `directory` | Multi-site job board | workready-jobs |

`portal-clean` and `directory` are the multi-site surfaces: the generator builds
`portal-clean` at the simulation root and `directory` at `/jobs/`.

Develop a theme standalone (uses committed fixtures in `src/data/`):

```bash
cd themes/tech-modern && npm install && npm run dev
```

## Repository layout

```
ensayo/
├── src/ensayo/          # Python package (CLI + generator)
│   ├── cli.py           # `ensayo` commands
│   ├── config.py        # YAML load + validation
│   ├── models.py        # company.yaml schema (Pydantic)
│   ├── prompts.py       # persona prompt + keyword builders
│   ├── content.py       # writes content/ and theme data
│   ├── generator.py     # orchestrates the Astro build
│   ├── themes.py        # theme discovery
│   └── shared/          # client assets (keyword-chatbot.js)
├── themes/<name>/       # Astro theme packages
├── examples/            # sample company.yaml configs
├── Dockerfile, docker-compose.yml, install.sh   # deployment (Phase 0)
└── pyproject.toml
```

## Contributing

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, the
project layout, and how to add a theme, archetype, or workflow.

## License

MIT — see [LICENSE](LICENSE).
