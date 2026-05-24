# ADR-0007: Lazy delivery for timed events; no background workers

**Status:** Accepted
**Source:** SPECIFICATION.md §3.4, §15.1, §15.5

## Context

Several features "happen later": a message arrives after a delay, task feedback is
released some minutes after submission, a scheduled group chat begins at a set
time, content unlocks at a phase boundary. The conventional answer is a background
worker plus a scheduler (Celery/RQ, cron, APScheduler, systemd timers). That adds
an always-on process, a broker, and a new class of failure — disproportionate for
a single-process, tens-of-users deployment ([ADR-0002](0002-single-fastapi-monolith.md)).

## Decision

Implement "happens later" as **lazy delivery**: persist a row with a `deliver_at`
timestamp and **filter on read**. When a client fetches its inbox/tasks/etc., the
API returns only rows whose `deliver_at` has passed. **No background workers, no
job queue, no scheduler.**

## Consequences

- **No extra moving parts** — nothing to run, supervise, or recover besides the one
  API process and SQLite.
- **Auditable and restart-safe** — the "schedule" is just data; a restart loses
  nothing and there are no in-flight jobs to reconcile.
- **Delivery is poll/read-time, not push.** Portals poll on an interval (~3s for
  chat). This is acceptable for the interaction model and avoids WebSocket/SSE
  infrastructure.
- **Proven pattern** — this is exactly how WorkReady handled timed delivery.

## Alternatives considered

- **Celery/RQ + broker.** Powerful but introduces Redis/broker ops and worker
  lifecycle management for no benefit at this scale.
- **cron / systemd timers / APScheduler.** Still an extra scheduled execution path,
  with its own failure and observability surface, to do what a `WHERE deliver_at <=
  now()` clause does for free.

> See SPECIFICATION.md §15.5 ("What Ensayo deliberately doesn't include") — this
> decision is part of a deliberate stance against background processing, real-time
> transport, and multi-process scaling.
