# Deployment Guide

Ensayo runs as a single VPS-hosted service (FastAPI + generator + dashboard) that
pushes student-facing static sites to GitHub Pages (see
[ADR-0001](../adr/0001-hosting-static-pages-dynamic-api.md)). There is one
deployment shape with three tiers.

## Tiers

| Tier | Adds | Needs |
|------|------|-------|
| **1 — Demo** | stub LLM, keyword chatbots, path-based routing, shared-password auth | Docker only |
| **2 — Standard** | real LLM, real chatbots, booking, custom domain | + LLM key + domain |
| **3 — Full** | AnythingLLM RAG, individual accounts, multi-site | + AnythingLLM |

## Zero-config first run

```bash
git clone https://github.com/<your-org>/ensayo.git
cd ensayo
docker compose up -d
# → http://localhost:8080   (dashboard at /admin/, student portal at /portal/)
```

The image ships Python, Node, Caddy, all themes (with vendored `node_modules`), and
a pre-built demo simulation — no API keys, no DNS, no internet needed beyond the
initial pull.

## Configured deployment (VPS)

```bash
cp instance.env.example instance.env   # domain, admin email, base URL (reviewable)
cp .env.example .env                   # secrets: LLM keys, GitHub token, JWT secret
docker compose up -d
docker compose exec ensayo ensayo admin create-uc --email you@uni.edu --admin
```

### Configuration files (spec §5.6)

`instance.env` (safe to review): `ENSAYO_DOMAIN`, `ADMIN_EMAIL`, `BASE_URL`,
`ENSAYO_HTTP_PORT`, `WORKING_CLONES_DIR`.

`.env` (secrets — never commit): `LLM_PROVIDER`, `LLM_MODEL`, the matching
`*_API_KEY`, `GITHUB_TOKEN`, `JWT_SECRET`, `ANYTHINGLLM_URL`/`ANYTHINGLLM_API_KEY`,
SMTP (`SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD`/`SMTP_FROM`).

Runtime data lives under `WORKING_CLONES_DIR` and `ENSAYO_DB` (SQLite); back these
up (VPS snapshot or `sqlite3 .backup`). They are never committed to git.

## Bare-metal

`install.sh` is the single source of truth (the Dockerfile runs the same script).
On a fresh Debian/Ubuntu VPS:

```bash
curl -fsSL https://raw.githubusercontent.com/<your-org>/ensayo/main/install.sh | bash
```

It installs Node 20, Caddy, the `ensayo` package, vendors theme deps, and builds the
demo. Idempotent (`SKIP_DEPS=1`, `SKIP_BUILD=1`). Upgrade by re-running it.

## GitHub Pages

When a UC publishes, the instance pushes the built site to the simulation repo's
`gh-pages` branch (a `.nojekyll` file is included so `_astro/` assets are served).
Enabling Pages is attempted via the API when `GITHUB_TOKEN` has rights; otherwise
enable it once in the repo settings (Pages → source: `gh-pages`).

- The instance needs a `GITHUB_TOKEN` with repo + Pages scope.
- A simulation is connected to a repo from the dashboard (**Publish** prompts for
  the URL) or created via the GitHub API.

## Cross-origin (GitHub Pages → VPS API)

Static sites on GitHub Pages call the VPS API for dynamic features. Set
`api_base_url` in the config to your VPS origin (e.g.
`https://ensayo.eduserver.au`); leave it empty when the API serves the site
(local/dev). Caddy injects CORS headers based on the configured domain.

## Custom domains

Point your domain's DNS at the VPS; Caddy obtains a TLS cert automatically
(Let's Encrypt) when domains are configured. Switching from Tier 1 (no DNS) to a
custom domain is a Caddy config change, not an application change. Per-site domains
for multi-site are future work; multi-site uses subpaths of one domain.

## AnythingLLM

For RAG-grounded LLM chatbots, run AnythingLLM (same Docker compose stack or
external) and set `ANYTHINGLLM_URL` + `ANYTHINGLLM_API_KEY`. Then **Provision
chatbots** from the dashboard. Without it, provisioning runs in dry-run mode and
employees use the keyword chatbot. Pin the AnythingLLM version.

## What Ensayo deliberately doesn't include

No background workers/queues (lazy delivery instead — ADR-0007), no multi-process
API (one uvicorn; SQLite WAL), no WebSocket/SSE (portals poll), no SaaS. See
SPECIFICATION.md §15.5.
