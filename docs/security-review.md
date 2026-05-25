# Security Review

A review of Ensayo's security posture as of the Phase 9 milestone. Scope: the
self-hosted VPS service, the generated static sites, and the data they handle.
Threat model (spec §3.4): the instance admin and UCs are **trusted**; the concern
is misconfiguration and student-facing exposure, not adversarial operators.

## Authentication & sessions

- **UC accounts:** passwords hashed with **bcrypt**; sessions are signed **JWTs**
  (HS256, 24h). Secret from `JWT_SECRET` (a dev fallback is used if unset — *set it
  in production*; JWT lib warns on short keys).
- **Students:** separate JWT (`typ=student`, 12h), scoped to one simulation slug;
  endpoints reject a token whose slug doesn't match the path. Three modes
  (shared-password / individual / email-only) are **all server-verified** — there
  is no client-side-only auth (ADR-0001). Email-only is explicitly low-assurance
  (documented).
- **Authorization:** simulation routes verify ownership (owner UC or
  `instance_admin`); student routes verify the student owns the resource.

✔ Recommendation followed: secrets only in `.env` / environment, never in YAML or
git. ⚠ Action for deployers: set a strong `JWT_SECRET`; use HTTPS (Caddy/Let's
Encrypt) so tokens aren't sent in clear.

## Secrets handling

- LLM/GitHub/AnythingLLM keys are read from environment variables; the per-sim
  `llm:` config stores only the *name* of the env var (`api_key_env`), never a key.
- Keys stay server-side: the static sites call the VPS LLM proxy; keys are never
  emitted to the browser.
- `.env` and `instance.env` are git-ignored.

## Data protection & privacy

- Student PII lives only in SQLite (never in the public git repo) — ADR-0005.
- **Soft delete** redacts PII (email/name nulled), anonymises bookings, and keeps
  referential integrity (spec §6.7). A hard-delete admin path is available for
  regulatory erasure.
- **Minors mode** removes PII collection (shared password), disables per-student
  logging (aggregate only), and is verifiable via the audience report (§7).
- Audit log drops per-student identifiers under `minors`.

## Web / transport

- **CORS:** the static origin (GitHub Pages / custom domain) calls the API origin;
  Caddy injects CORS headers per configured domain (Tier 1 is wildcard for local
  demo only — tighten for production).
- **TLS:** Caddy obtains certs automatically when domains are configured.
- **Static output:** pure HTML/CSS/JS; the keyword chatbot runs client-side with no
  network. `.nojekyll` is added on publish; no secrets are baked into `dist/`.

## Injection & untrusted input

- **SQL:** all queries use parameterised statements (no string interpolation of
  user input).
- **Prompt injection:** chatbot personas are *simulation context, not security
  context* (spec §15.3) — "breaking character" is annoying, not dangerous. System
  prompts include stay-in-character instructions; minors get keyword chatbots only.
- **Student free-text** (chat, submissions) is **not** moderated by the platform —
  moderation is the UC's responsibility, which is why minors mode disables most
  free-input surfaces (documented in Safe Mode).
- **Path traversal:** the `/sims/<slug>/<path>` server resolves and confirms the
  target stays within the simulation's `dist/` before serving.

## Operational / availability

- Single uvicorn process + SQLite (WAL). Assumed load is tens of concurrent users;
  not designed for adversarial load or horizontal scale (spec §15.5). Put it behind
  a reverse proxy / rate limiting if exposed broadly.
- Git push from the dashboard can fail (network/auth); the working clone is left
  consistent for retry.

## Known limitations (accepted)

- Booking-gated chat is a **UX gate** (client-side), not a security boundary;
  server-enforced gating is the visibility-rules system.
- AnythingLLM embed widgets are public by design (workspace prompt controls
  behaviour, not access).
- The dev `JWT_SECRET` fallback must be overridden in production.

## Summary

No high-severity issues for the stated threat model. The main deployer
responsibilities are: set `JWT_SECRET`, serve over HTTPS, scope CORS for
production, and obtain institutional clearance before using individual-account
(PII) mode. These are documented in the [Deployment](guides/deployment.md) and
[Safe Mode](guides/safe-mode.md) guides.
