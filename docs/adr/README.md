# Architecture Decision Records

These ADRs capture the **load-bearing architectural decisions** for Ensayo and
the reasoning behind them. They are distilled from the canonical specification
([`../SPECIFICATION.md`](../SPECIFICATION.md), the v2 design), specifically its
"Decisions Made" table (§15.1) and Architecture Overview (§3).

An ADR is a short document that records one decision: the context that forced a
choice, the decision taken, and the consequences we accept as a result. They
exist so a newcomer (human or AI) can understand *why* the code is shaped the way
it is without re-deriving it from the 2,500-line spec.

> **Specification versioning:** v2 is canonical and the only version maintained
> going forward. v1 is superseded and kept only as a historical artifact outside
> this repository. When the design changes, update the spec **and** add or amend
> an ADR — don't let them drift.

## Index

| ADR | Decision | Status |
|-----|----------|--------|
| [0001](0001-hosting-static-pages-dynamic-api.md) | Static student sites on GitHub Pages; dynamic API on a VPS | Accepted |
| [0002](0002-single-fastapi-monolith.md) | One FastAPI modular monolith on the VPS (not microservices) | Accepted |
| [0003](0003-docker-default-deploy.md) | Docker image is the default deploy; `install.sh` is the single source of truth | Accepted |
| [0004](0004-astro-theme-packages.md) | Themes are full Astro packages, not parameterised templates | Accepted |
| [0005](0005-yaml-canonical-sqlite-runtime.md) | YAML in git is canonical for content; SQLite is canonical for runtime | Accepted |
| [0006](0006-open-self-host-no-saas.md) | Open self-host; no multi-tenant SaaS | Accepted |
| [0007](0007-lazy-delivery-no-workers.md) | Lazy delivery for timed events; no background workers | Accepted |

## Format

Each ADR follows a lightweight Nygard structure: **Context → Decision →
Consequences**, with **Alternatives considered** where the rejected options are
instructive. Status is one of `Proposed`, `Accepted`, `Superseded by ADR-NNNN`.
