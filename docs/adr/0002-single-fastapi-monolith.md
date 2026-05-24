# ADR-0002: One FastAPI modular monolith on the VPS

**Status:** Accepted
**Source:** SPECIFICATION.md §3.2, §3.4, §15.1

## Context

The dynamic side has many surfaces: dashboard, student auth, booking, in-app
messaging, 1-on-1 conversations, group chat, task submission, workflow, LLM
proxy, AnythingLLM provisioning. The platform's assumed scale is **tens of
concurrent users per simulation**, not thousands — a department running a class
or two at a time, not an internet-scale service.

## Decision

Build a **single FastAPI application** ("Ensayo Services") with internal routers
organised by surface (`/admin/`, `/api/v1/auth/`, `/api/v1/bookings/`, …). The
generator is imported as a Python library by this app (and also exposed as the
`ensayo` CLI). Persistence is **SQLite** in WAL mode. One uvicorn process.

## Consequences

- **Simplest possible operations:** one process, one DB file, one deployment unit.
  Backups are a file copy. No service mesh, no broker, no orchestration.
- **Routers provide internal modularity** without distributed-systems overhead.
- **SQLite + WAL** gives enough read concurrency for the assumed load. Schema
  evolves via idempotent on-startup migrations (`_migrate()` adds columns
  `IF NOT EXISTS`) — no separate migration tool, safe to re-run.
- **No horizontal scaling.** Scaling out would require re-architecting around
  PostgreSQL and multiple processes. We explicitly do **not** design for that
  (see SPECIFICATION.md §15.5).
- **No multi-process API**, no WebSocket/SSE — portals poll; lazy delivery
  (see [ADR-0007](0007-lazy-delivery-no-workers.md)) covers "happens later".

## Alternatives considered

- **Microservices.** Operationally disproportionate for tens of users; introduces
  network boundaries, deployment complexity, and distributed failure modes for no
  benefit at this scale.
- **Serverless functions.** Cold starts hurt LLM-proxy latency; SQLite + local git
  working clones don't fit an ephemeral filesystem model.
- **PostgreSQL from day one.** Adds an always-on service and ops burden the
  assumed load doesn't warrant. The migration path stays open if scale changes.
