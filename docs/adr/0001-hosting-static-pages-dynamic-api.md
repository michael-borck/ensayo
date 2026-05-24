# ADR-0001: Static student sites on GitHub Pages; dynamic API on a VPS

**Status:** Accepted
**Source:** SPECIFICATION.md §1, §3, §5

## Context

A simulation has two very different kinds of surface:

- **Student-facing pages** — corporate website, staff directory, document
  library, employee profiles. These are read-heavy and, during a class, can be
  hit by a whole cohort at once.
- **Dynamic features** — booking, authentication, LLM chat, the lecturer
  dashboard, conversation/task state. These need server-side code, secrets (LLM
  and git tokens), and a database.

We need hosting that is cheap and effortless for the read-heavy surface, and a
controlled server for the dynamic surface where secrets and student PII can live.
A previous framing offered a "purely static" deployment with client-side auth
gates; those are trivially bypassable and unsuitable for assessment.

## Decision

Split the system along the static/dynamic line:

- **Student-facing sites are pure static HTML/CSS/JS, served by GitHub Pages.**
  The generator produces a `dist/` and the VPS pushes it to a GitHub repo
  (one repo per simulation).
- **All dynamic features live in a single VPS-hosted service.** The static
  site's browser JavaScript calls the VPS API (`/api/v1/*`) for anything dynamic.
- **There is no purely-static deployment.** Authentication is always
  server-verified by the VPS; the static site never trusts client-side state for
  access decisions.

## Consequences

- **Free, effectively infinite static hosting.** A 300-student cohort browsing
  pages puts zero load on the VPS.
- **The VPS only handles light dynamic traffic** (tens of concurrent users),
  which justifies SQLite and a single process (see [ADR-0002](0002-single-fastapi-monolith.md)).
- **Secrets stay server-side.** LLM keys and git tokens never reach the browser;
  the VPS proxies LLM calls.
- **Cross-origin is real.** The static origin (GitHub Pages / custom domain)
  calls the API origin (VPS). Caddy injects CORS headers per simulation so the
  API stays generic.
- **The generator must produce base-path-aware URLs** so a site works at a domain
  root *or* under a subpath (`/sims/<slug>/`) for multi-site and path routing.
- **Two deploy targets** (push to GitHub + run the VPS) instead of one. Accepted
  in exchange for the scaling and cost properties above.

## Alternatives considered

- **Everything on the VPS (server-rendered).** Simpler mental model, but the VPS
  now serves all student page traffic and we lose free static hosting and CDN-like
  behaviour.
- **Purely static (no VPS).** Can't do server-verified auth, booking, server-side
  content gating, or keep LLM keys secret. Rejected.
