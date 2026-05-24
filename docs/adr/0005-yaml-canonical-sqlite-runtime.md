# ADR-0005: YAML in git is canonical for content; SQLite is canonical for runtime

**Status:** Accepted
**Source:** SPECIFICATION.md §3.3, §4.3, §15.1

## Context

Ensayo holds two fundamentally different kinds of data:

- **Authored content** — companies, employees, personas, documents, scenario,
  branding, theme choice. Edited deliberately, benefits from review and history.
- **Runtime state** — bookings, student accounts, conversation transcripts, task
  submissions, messages. High-frequency, volatile, and PII-sensitive.

An earlier design left it ambiguous whether YAML files or the database were the
source of truth, which makes recovery and editing semantics unclear.

## Decision

Establish explicit, non-overlapping ownership:

- **YAML + Markdown + persona `.txt` files in the simulation's git repo are
  canonical for content.** The generator's `dist/` is derived from them. The API
  reads persona prompts from disk at runtime (`SITES_DIR`).
- **SQLite on the VPS is canonical for runtime state**, and *additionally* holds a
  **rebuildable cache** of content metadata for fast dashboard reads.
- On a content edit, the dashboard writes YAML in the working clone, regenerates
  affected `dist/`, commits, pushes, then updates the DB cache.

## Consequences

- **Free version control for content** — UCs get rollback, diff, and blame via git.
- **Portability** — a simulation is just a git repo; another instance can clone and
  run it.
- **Resilience** — losing the SQLite DB loses no authored content (rebuild the
  cache with `ensayo ingest`); losing git but keeping the DB allows last-resort
  re-serialisation back to YAML.
- **PII stays out of git** — volatile, sensitive student data lives only in SQLite,
  which is backed up separately and never committed.
- **Cost:** the cache must be kept in sync when YAML changes (a deliberate step in
  the edit flow), and the edit flow is therefore synchronous (edit → regenerate →
  commit → push → update cache).

## Alternatives considered

- **Database as the single source of truth** (content in SQLite, export YAML on
  demand). Loses git-native review/rollback/portability and puts authored content
  at risk if the DB is lost.
- **Files as the single source of truth** (no DB). Runtime state (bookings,
  transcripts) doesn't belong in a public git repo and needs transactional,
  queryable storage.
