# ADR-0008: Declarative workflow engine (Phase 7 spike — GATE PASSED)

**Status:** Accepted
**Source:** SPECIFICATION.md §14 (Phase 7), §15.1; Phase 7 spike

## Context

Multi-site simulations (Phase 8) need a way to describe a student's lifecycle —
the stages they move through and which interaction surfaces (messaging, booking,
1-on-1 conversation, group chat, tasks, assessment) are active at each. WorkReady
hard-coded one internship lifecycle in Python. We want one engine that drives
*any* domain (internship, healthcare, finance) without code changes.

Spec §15.1 chose a **declarative** engine, *to be validated by a Phase 7 spike
before committing to multi-site*. This ADR records the spike result and the gate
decision. Phase 8 could not start until this was resolved.

## The spike

Implemented `ensayo.workflow`: a `workflow.yaml` describes `stages`, each with
`surfaces` and `on_enter` actions, connected by `transitions` (`event` + optional
`when` context guard). The engine (`advance`, `run`) is ~120 lines and entirely
domain-agnostic. Two workflows were authored as YAML only:

- **internship** — application → interview → placement → exit interview
- **medical_network** — triage → consultation → ward round → discharge

Both run end-to-end with stub events (`ensayo workflow run -w <name> -e ...`).
The **same six surfaces** activate at **different stages** across the two domains
— e.g. `conversation` powers the internship *interview* and the medical
*consultation*; `group_chat` powers the internship *placement* and the medical
*ward round* — with **no code change between them**, only different YAML. 12
tests cover loading, validation, both happy/branch paths, guards, terminal stops,
and the domain-independence claim.

## Decision

**Continue with the declarative engine. No Python-plugin mechanism is needed for
workflow orchestration.** The schema is sufficient to express stage progression,
per-stage surface activation, branching, and entry actions across domains.

The key design boundary that makes this work — the **escape hatch** — is:

> The **runtime computes events and their context**; the **workflow only routes**.

Domain-specific computation (e.g. "did the interview pass?" from an LLM
assessment score, "admit or discharge?" from a clinical decision) happens in the
**surface handlers** (Phase 8), which then emit an event with context
(`interview_result` + `{outcome: pass}`). The workflow stays pure data: it matches
the event and guard and moves to the next stage. No arbitrary code runs inside the
workflow; there is no `eval` of expressions — guards are plain key/value matches.

## Consequences

- **Phase 8 is unblocked.** The lifecycle of every multi-site domain is authored
  as YAML; the engine is shared and tested.
- **Actions are descriptors, not code.** `on_enter` emits structured actions
  (`{type: notify, ...}`, `{type: assign_tasks}`); the Phase 8 runtime dispatches
  them to the notification adapter / surfaces. Adding an action type is a runtime
  change, not an engine change.
- **Guards are intentionally limited** to equality on event context. If a future
  workflow needs richer conditions, the preferred path is still "compute it in the
  handler, pass the result as context" rather than adding an expression language.
- **YAML footgun noted:** transition keys use `event:` (not `on:`) because YAML 1.1
  parses `on`/`off`/`yes`/`no` as booleans.

## Alternatives considered

- **Procedural (Python) workflows per domain.** What WorkReady did; every new
  domain is code. Rejected — defeats the configuration-over-code principle.
- **Declarative + Python-plugin callbacks for transitions.** Considered as the
  escape hatch. The spike showed it unnecessary: the event/context boundary keeps
  all domain logic in handlers while the workflow stays declarative. Can be revisited
  if a concrete workflow proves inexpressible.
- **An expression language for guards** (e.g. CEL). Over-engineered for the need;
  `when:` equality plus handler-computed context covers the observed cases.
