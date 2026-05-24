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

| Theme         | For                              | Source (reference) |
|---------------|----------------------------------|--------------------|
| `tech-modern` | Technology / SaaS companies      | nexuspoint-systems |

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
