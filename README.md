# Ensayo

Configuration-driven generator for **LLM-assisted workplace teaching simulations**.

A *simulation* is a fictional organisation rendered as a website where students
interact with virtual employees (chatbots), read internal documents, and complete
scenario-driven tasks — in a safe, controlled environment. A lecturer describes
the company in `company.yaml` (or, later, through a dashboard) and Ensayo produces
a complete, deployable static site.

This repository is the platform itself — the generator that *produces*
simulations, not a single simulation.

## Documentation

- [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md) — the canonical (v2) design.
- [`docs/architecture.md`](docs/architecture.md) — the short, navigable overview.
- [`docs/adr/`](docs/adr/) — Architecture Decision Records (why it's built this way).
- [`CONTEXT.md`](CONTEXT.md) — domain vocabulary used throughout the code.

> **Status: Phase 0 (Foundation).** This is the first slice of a phased build.
> What works today: the `ensayo` CLI, `company.yaml` loading + validation, content
> generation (employee personas, prompts, documents), one Astro theme
> (`tech-modern`), and a deterministic keyword chatbot. The FastAPI dashboard,
> LLM-assisted generation, AnythingLLM, multi-site, and the rest follow in later
> phases (see the roadmap in the spec, §14).

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

Two further themes — `portal-clean` (student portal) and `directory` (job
board / hub) — are *multi-site* surfaces and ship with **Phase 8** (multi-site),
where the portal/jobs data they render exists.

Develop a theme standalone (uses committed fixtures in `src/data/`):

```bash
cd themes/tech-modern && npm install && npm run dev
```

More themes (`portal-clean`, `directory`, `finance-traditional`, …) land in later
phases per the spec roadmap.

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

## License

MIT — see [LICENSE](LICENSE).
