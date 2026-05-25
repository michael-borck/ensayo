# Contributing to Ensayo

Thanks for your interest! Ensayo is an open, self-hosted platform — contributions
of themes, archetypes, docs, and fixes are all welcome.

## Development setup

Requirements: **Python 3.12+** ([uv](https://docs.astral.sh/uv/) recommended) and
**Node 20+** (only to build Astro themes).

```bash
git clone https://github.com/michael-borck/ensayo.git
cd ensayo
uv run ensayo --version          # installs deps into a venv on first run
uv run --with pytest pytest -q   # run the test suite (105 tests)
```

Useful commands:

```bash
uv run ensayo validate -c examples/nexuspoint/company.yaml
uv run ensayo generate -c examples/nexuspoint/company.yaml -o ./out   # build a site
uv run ensayo gallery -o ./gallery                                    # all themes
uv run ensayo serve                                                   # API + dashboard
```

## Project layout

```
src/ensayo/          Python: CLI, generator, models, LLM, workflow, library
src/ensayo/api/      FastAPI service, dashboard + student portal SPAs
themes/<name>/       Astro theme packages
docs/                Spec, architecture, ADRs, and the guides/
tests/               pytest (one file per phase)
```

Start with [`docs/architecture.md`](docs/architecture.md) and
[`CONTEXT.md`](CONTEXT.md) for the mental model and domain vocabulary.

## How to contribute common things

- **A new theme** — see [Theme Authoring](docs/guides/theme-authoring.md). Commit
  the theme's `package-lock.json`; never commit `node_modules`.
- **A new role archetype** — see [Archetype Authoring](docs/guides/archetype-authoring.md).
- **A new workflow** — add `src/ensayo/library/workflows/<name>.yaml`
  (transition key is `event:`, not `on:`).

## Conventions

- **Tests first-class.** Add/keep tests green (`pytest -q`). API tests use
  `fastapi.testclient`; pass `build: false` to avoid needing Node.
- **Architecture decisions** go in `docs/adr/` as a new ADR; keep the spec and
  ADRs in sync when behaviour changes.
- **Migrations** are idempotent and on-startup (`api/db.py`): add columns with the
  `_add_column` helper; never drop/rewrite existing data.
- **No new always-on services.** "Happens later" uses lazy delivery (`deliver_at`),
  not background workers (see [ADR-0007](docs/adr/0007-lazy-delivery-no-workers.md)).
- **Secrets** only via environment / `.env` — never in YAML or committed files.

## Pull requests

Keep PRs focused, describe the change and why, and note any new env vars or
migrations. Run the suite before opening.

## License

By contributing you agree your contributions are licensed under the
[MIT License](LICENSE).
