# ADR-0006: Open self-host; no multi-tenant SaaS

**Status:** Accepted
**Source:** SPECIFICATION.md §1, §15.1

## Context

Ensayo could be offered as a hosted, multi-tenant SaaS (we run it; institutions
sign up) or as open-source software that each institution deploys itself. The
users span universities, schools, and individual educators, several of whom have
strict data-residency and procurement constraints.

## Decision

Ensayo is **open-source and self-hosted**. Anyone — an institution or a solo
educator — deploys their own instance on their own VPS (or laptop). There is **no
central hosted service and no multi-tenant SaaS**. Within a single instance,
multiple Unit Coordinators and units share the same infrastructure and can
co-coordinate simulations.

## Consequences

- **No per-seat fees, no vendor lock-in, no data egress.** Student data never
  leaves the institution's own infrastructure.
- **Lower institutional approval burden** — one VPS approval covers every
  simulation a department runs, and there is no third-party processor to vet.
- **The deployer owns operations and compliance** — backups, uptime, and privacy
  obligations are theirs. The platform provides the mechanisms (audience modes,
  auth modes, data export/delete); policy compliance is the deployer's
  responsibility.
- **No central telemetry or cross-instance features.** Instances are independent;
  federation between instances is explicitly out of scope for now.

## Alternatives considered

- **Hosted multi-tenant SaaS.** Convenient for users but creates a data-processor
  relationship many institutions can't accept, plus subscription/lock-in concerns
  and an ops/business burden orthogonal to the educational goal.
