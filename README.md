# Ensayo

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.12%2B-3776ab)
![tests](https://img.shields.io/badge/tests-157%20passing-brightgreen)
![stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20Astro-111)

**Turn a worksheet into a living workplace simulation.**

A lecturer describes a fictional company (or drops in an assignment) and Ensayo
builds a website where students interview chatbot employees, read internal
documents, and work through scenario-driven tasks — in a safe, controlled
environment. It's a generator platform: one install serves many lecturers, each
with their own simulations.

---

## Deploy in 5 minutes (Docker — recommended)

```bash
git clone https://github.com/michael-borck/ensayo.git
cd ensayo
cp instance.env.example instance.env    # then edit (see below)
docker compose up -d                    # → http://localhost:8080/admin/
docker compose exec ensayo ensayo admin create-uc -e you@uni.edu -p 'secret' --admin
```

Open `http://localhost:8080/admin/` and log in. That's it.

**Minimum `instance.env` for a working deploy:**
```ini
JWT_SECRET=<run: openssl rand -hex 32>
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_xxxxxxxx
RESEND_FROM=Ensayo <noreply@your-verified-domain.com>
ALLOWED_DOMAINS=your.uni.edu
```

Put Cloudflare (DNS or Tunnel) → your box's `:8080`, served at the domain root.

---

## Self-host alternative (bare-metal)

```bash
git clone https://github.com/michael-borck/ensayo.git
cd ensayo
uv sync                                 # installs ensayo + all deps (uv fetches Python)
cp .env.example .env                    # then edit (same vars as above)
uv run ensayo admin create-uc -e you@uni.edu -p 'secret' --admin
uv run ensayo serve --host 127.0.0.1 --port 8000    # → http://127.0.0.1:8000/admin/
```

Node 20 is also needed if you'll build simulations on this box:
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt install -y nodejs
```

Or use the setup script (installs uv + Node + deps + creates admin):
```bash
git clone https://github.com/michael-borck/ensayo.git && cd ensayo
bash deploy/selfhost.sh
```

Put a reverse proxy (Caddy / nginx / Cloudflare Tunnel) → `127.0.0.1:8000`,
served at the domain root. HTTPS is required (passwords/tokens in transit).

---

## Configuration

All config lives in **`.env`** (bare-metal) or **`instance.env`** (Docker).
Both are gitignored.

| Variable | Required | Default | What it does |
|----------|----------|---------|-------------|
| `JWT_SECRET` | **Yes** | (dev fallback) | Session-signing secret. Use `openssl rand -hex 32`. |
| `EMAIL_PROVIDER` | No | `console` | `resend`, `smtp`, or `console` (codes shown in admin panel). |
| `RESEND_API_KEY` | If resend | — | Resend API key (`re_…`). |
| `RESEND_FROM` | If resend | — | Sender address on a verified Resend domain. |
| `SMTP_HOST` | If smtp | — | SMTP relay host (Gmail/SendGrid/institutional). |
| `SMTP_PORT` | If smtp | `587` | SMTP port (`465` + `SMTP_SSL=true` for implicit TLS). |
| `SMTP_USER` / `SMTP_PASSWORD` | If smtp | — | SMTP credentials. |
| `EMAIL_FROM` | No | `ensayo@localhost` | Shared From address (smtp/resend). |
| `ALLOWED_DOMAINS` | No | (open) | Comma-separated email domains allowed to self-register. |
| `MAX_SIMS_PER_UC` | No | `3` | Per-account simulation cap. |
| `MAX_CONCURRENT_BUILDS` | No | `2` | Concurrent sim builds; extras defer. |
| `GITHUB_TOKEN` | No | — | Set to show the GitHub Publish button (hidden otherwise). |
| `ENSAYO_DB` | No | `./.ensayo-data/ensayo.db` | SQLite database path. |
| `WORKING_CLONES_DIR` | No | `./.ensayo-data/sims` | Where sim working clones live. |
| `LLM_PROVIDER` | No | `stub` | LLM for content generation + ideation (`stub`/`openai`/`anthropic`/`gemini`/…). |

Verify email delivery after configuring:
```bash
uv run ensayo admin send-test-email --to you@uni.edu
```

---

## Admin operations

All via the `ensayo admin` CLI or the dashboard's **Instance admin** panel.

| Operation | CLI | Dashboard |
|-----------|-----|-----------|
| **Create admin** | `ensayo admin create-uc -e you@uni.edu -p 'pw' --admin` | — |
| **Create lecturer** | `ensayo admin create-uc -e them@uni.edu -p 'pw'` | Self-registration via landing page |
| **Promote to admin** | `ensayo admin promote -e them@uni.edu` | — |
| **Test email** | `ensayo admin send-test-email --to you@uni.edu` | — |
| **Maintenance mode** | — | Checkbox in Instance admin panel (live toggle, no restart) |
| **Freeze registration** | — | Checkbox in Instance admin panel |
| **Sim limit** | `MAX_SIMS_PER_UC=3` in `.env` | Shown as "X of 3 used" |

### Maintenance mode
Toggle from the dashboard → **Instance admin → Maintenance mode**. When ON:
- `/` shows a "coming soon" page to the public.
- `/preview/` always shows the real landing (your testing URL).
- `/admin/` always works.

### Promote an existing account
If a lecturer already registered (via the landing page) and you want them as admin:
```bash
uv run ensayo admin promote -e them@uni.edu
```

---

## Features

### Self-registration (lecturer sign-up)
Lecturers register from the landing page with an allowed-domain email, receive a
6-digit verification code, verify, and log in. No admin CLI needed for ongoing
account creation. Registration can be frozen live from the dashboard.

### Landing page
A public landing page at `/` with a hero, feature cards, self-host instructions,
and a login/register overlay (Wix-style). Logged-in users see "Go to dashboard".

### Ideation (idea → simulation)
Type an idea or upload a file (txt/md/qmd/pdf/docx/pptx/xlsx/odt) → Ensayo
proposes 2–3 simulations as accordions (single-company, multi-site, school-safe),
each with pattern, company, theme, scenario, employees, pros/cons. Pick one →
it pre-fills the editor → build.

### Tabbed simulation editor
A Wix-style tabbed editor (Basics · Company · Scenario · People · Documents ·
Features · Advanced YAML) for creating and editing simulations. No raw YAML
required; the Advanced tab is a power-user escape hatch.

### Persona editor
Each employee is an expandable card with layered personality:
- **Archetype** (dropdown — sets the baseline).
- **Background / backstory** (textarea).
- **Personality quirks** (clickable pills, archetype-aware + custom input).
- **Opinions** (scenario-typed suggestions + custom).
- **Scenario perspective** (one-click templates + free text).

These compose into the system prompt via the layered prompt builder
(archetype → industry → company → individual).

### Multi-site simulations
A portal coordinating several company sites (one repo, subpaths). The dashboard
supports creating + editing multi-site sims via a master-detail editor that
reuses the per-company editor.

### Safe mode (minors)
Choosing `minors` as the audience enforces a safe bundle: keyword-only chatbots,
shared-password sign-in, LLM-assist off, single-company only.

### Per-account sim limit
`MAX_SIMS_PER_UC` (default 3) caps simulations per account. Shown as "X of 3
used" in the dashboard; "+ New" disables at the cap.

### Build concurrency cap
`MAX_CONCURRENT_BUILDS` (default 2) prevents a flood of concurrent builds from
exhausting the box. Builds beyond the cap defer and show "build deferred".

---

## Architecture

```
Lecturer ──► Landing page (/) ──► Dashboard (/admin/)
                                      │
                    create/edit sim ──► ensayo generator (Python)
                                      │                  │
                              content/ (canonical)   dist/ (static site)
                                      │                  │
                              git working clone    served at /sims/<slug>/
                                      │
                    Student ──► /sims/<slug>/ ──► API (/api/v1/*) for dynamic features
```

- **Python** orchestrates: config validation, content generation, theme build.
- **Astro themes** (8) are full packages with templates + scoped CSS. Node is
  build-time only; the deployed site is pure static HTML/CSS/JS.
- **Keyword chatbots** run client-side (no LLM, no network) — the default and
  the minors-safe option.
- **LLM chatbots** call back to the VPS API (or AnythingLLM for RAG).
- **SQLite** (WAL) holds runtime state; single-process, single-box.

---

## Themes

| Theme | For |
|-------|-----|
| `tech-modern` | Technology / SaaS |
| `finance-traditional` | Finance & professional services |
| `mining-rugged` | Mining, resources, heavy industry |
| `nfp-warm` | Charities, NFPs, social enterprise |
| `government-formal` | Government & public sector |
| `advisory-cool` | Consulting & advisory |
| `portal-clean` | Multi-site hub |
| `directory` | Multi-site job board |

---

## Repository layout

```
ensayo/
├── src/ensayo/           # Python package (CLI + generator + API)
│   ├── cli.py            # ensayo commands
│   ├── generator.py      # orchestrate the Astro build
│   ├── ideate.py         # idea/file → simulation proposals
│   ├── extract.py        # file → text (multi-format)
│   ├── api/              # FastAPI service + dashboard
│   │   ├── app.py        # routes
│   │   ├── service.py    # simulation lifecycle
│   │   ├── registration.py # self-registration + maintenance
│   │   ├── email.py      # provider switch (console/smtp/resend)
│   │   └── static/       # landing + dashboard + maintenance pages
│   └── themes.py         # theme discovery
├── themes/<name>/        # 8 Astro theme packages
├── deploy/               # Caddyfile, entrypoint, selfhost.sh
├── Dockerfile            # full-service image
├── docker-compose.yml    # one-command deploy
└── pyproject.toml
```

---

## License

MIT — see [LICENSE](LICENSE).
