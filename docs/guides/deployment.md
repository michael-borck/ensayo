# Deployment Guide

Ensayo is a **Wix-like hosted platform** — one install serves many lecturers, each
building simulations that students access at `/sims/<slug>/` on the same server.
No GitHub Pages required for the default flow; GitHub publishing is an
advanced/hidden feature.

## Quick deploy (Docker — 5 minutes)

```bash
git clone https://github.com/michael-borck/ensayo.git
cd ensayo
cp instance.env.example instance.env    # edit: JWT_SECRET, email, ALLOWED_DOMAINS
docker compose up -d                    # → http://localhost:8080/admin/
docker compose exec ensayo ensayo admin create-uc -e you@uni.edu -p 'secret' --admin
```

The image runs uvicorn (FastAPI) + Caddy (reverse-proxy) via a single entrypoint.
Student simulations are served at `/sims/<slug>/`; the dashboard is at `/admin/`.

### Minimum `instance.env`

```ini
JWT_SECRET=<openssl rand -hex 32>
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_xxxxxxxx
RESEND_FROM=Ensayo <noreply@your-verified-domain.com>
ALLOWED_DOMAINS=your.uni.edu
```

Put Cloudflare (DNS or Tunnel) or a reverse proxy → your box's `:8080`.

## Self-host (bare-metal)

```bash
git clone https://github.com/michael-borck/ensayo.git
cd ensayo
uv sync                                 # installs ensayo + all deps
cp .env.example .env                    # edit (same vars as above)
uv run ensayo admin create-uc -e you@uni.edu -p 'secret' --admin
uv run ensayo serve --host 127.0.0.1 --port 8000    # → /admin/
```

Node 20 is also needed if you'll build simulations on this box (Astro build-time
only; the deployed site is pure static HTML/CSS/JS):

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt install -y nodejs
```

Or use the setup script (installs uv + Node + deps + creates admin):

```bash
git clone https://github.com/michael-borck/ensayo.git && cd ensayo
bash deploy/selfhost.sh
```

Put a reverse proxy (Caddy / nginx / Cloudflare Tunnel) → `127.0.0.1:8000`.
HTTPS is required (passwords/tokens in transit).

## Configuration

All config lives in **`.env`** (bare-metal) or **`instance.env`** (Docker).
Both are gitignored.

### Required

| Variable | What it does |
|----------|-------------|
| `JWT_SECRET` | Session-signing secret. Use `openssl rand -hex 32`. |
| `EMAIL_PROVIDER` | `resend`, `smtp`, or `console` (codes shown in admin panel). |
| `ALLOWED_DOMAINS` | Comma-separated email domains allowed to self-register. Empty = open. |

### Email

| Variable | Provider | What it does |
|----------|----------|-------------|
| `RESEND_API_KEY` | resend | Resend API key (`re_…`). |
| `RESEND_FROM` | resend | Sender address on a verified Resend domain. |
| `SMTP_HOST` | smtp | SMTP relay host (Gmail/SendGrid/institutional). |
| `SMTP_PORT` | smtp | SMTP port (`465` + `SMTP_SSL=true` for implicit TLS). |
| `SMTP_SSL` | smtp | Set `true` for port 465 (implicit TLS); omit for 587 (STARTTLS). |
| `SMTP_USER` / `SMTP_PASSWORD` | smtp | SMTP credentials. |
| `EMAIL_FROM` | smtp | Shared From address. |

Verify delivery after configuring:

```bash
uv run ensayo admin send-test-email --to you@uni.edu
```

### Simulation management

| Variable | Default | What it does |
|----------|---------|-------------|
| `MAX_SIMS_PER_UC` | `3` | Per-account simulation cap. |
| `MAX_CONCURRENT_BUILDS` | `2` | Concurrent sim builds; extras defer. |
| `ENSAYO_DB` | `./.ensayo-data/ensayo.db` | SQLite database path. |
| `WORKING_CLONES_DIR` | `./.ensayo-data/sims` | Where sim working clones live. |

### LLM (content generation + ideation)

| Variable | Default | What it does |
|----------|---------|-------------|
| `LLM_PROVIDER` | `stub` | `stub`/`openai`/`anthropic`/`gemini`/`ollama`/`openrouter`/`lmstudio`. |
| `LLM_MODEL` | — | Model name (e.g. `claude-sonnet-4-6`). |
| `<PROVIDER>_API_KEY` | — | The key matching `LLM_PROVIDER`. |

Without an LLM key, Ensayo runs in stub mode: template-generated content,
keyword chatbots only, ideation uses a keyword-derived fallback.

### AnythingLLM (LLM chatbots + per-persona RAG)

| Variable | What it does |
|----------|-------------|
| `ANYTHINGLLM_URL` | AnythingLLM base URL (e.g. `http://anythingllm:3001`). |
| `ANYTHINGLLM_API_KEY` | AnythingLLM API key. |
| `ANYTHINGLLM_ALLOWLIST_DOMAINS` | Comma-separated domains allowed to use embed widgets. |

When configured, **Provision chatbots** from the dashboard creates per-persona
workspaces with targeted RAG: each persona gets only the documents they "know"
(Phase 3 doc↔persona mapping) plus their backstory. Without AnythingLLM,
provisioning runs in dry-run mode and personas use keyword chatbots.

### GitHub publishing (advanced — hidden by default)

| Variable | What it does |
|----------|-------------|
| `GITHUB_TOKEN` | Set to show the GitHub Publish button in the dashboard. |

Leave unset to hide GitHub entirely (Wix-like model: sims served from the VPS).

## Admin operations

All via the `ensayo admin` CLI or the dashboard's **Instance admin** panel.

```bash
# Create admin
ensayo admin create-uc -e you@uni.edu -p 'pw' --admin

# Promote existing lecturer to admin
ensayo admin promote -e them@uni.edu

# Verify email delivery
ensayo admin send-test-email --to you@uni.edu
```

| Operation | How |
|-----------|-----|
| **Maintenance mode** | Dashboard → Instance admin → Maintenance mode (live toggle). `/` shows coming-soon; `/preview/` always shows the real landing. |
| **Freeze registration** | Dashboard → Instance admin → Registration open (live toggle). |
| **Sim limit** | `MAX_SIMS_PER_UC=3` in `.env` / `instance.env`. Shown as "X of 3 used". |

## Backup

Runtime data lives in two places — back up both:

| Path | Contents |
|------|----------|
| `ENSAYO_DB` (`ensayo.db`) | All accounts, simulations, config caches, settings. |
| `WORKING_CLONES_DIR` (`sims/`) | Git working clones + built static sites. |

```bash
# SQLite backup (safe while running)
sqlite3 .ensayo-data/ensayo.db ".backup .ensayo-data/ensayo-backup.db"

# Or VPS snapshot / volume backup for Docker deployments
```

These are never committed to git.

## Behind a reverse proxy

Ensayo listens on `127.0.0.1:8000` (bare-metal) or `:8080` (Docker). Put a
reverse proxy in front for TLS termination:

**Caddy** (automatic HTTPS via Let's Encrypt):
```caddyfile
ensayo.yourdomain.org {
    reverse_proxy 127.0.0.1:8000
}
```

**Cloudflare Tunnel** (no open ports):
```bash
cloudflared tunnel --url http://localhost:8000
```

**nginx**: standard `proxy_pass` to the upstream; terminate TLS with certbot.

The Docker image includes its own Caddy (`deploy/Caddyfile.service`) that
reverse-proxies `:80` → `:8000` inside the container. Map `ENSAYO_HTTP_PORT`
(default 8080) to expose it.

## What Ensayo deliberately doesn't include

No background workers/queues (lazy delivery), no multi-process API (one uvicorn;
SQLite WAL), no WebSocket/SSE (portals poll), no SaaS dependencies. See
[architecture.md](../architecture.md) for the full rationale.
