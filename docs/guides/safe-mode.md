# Safe Mode Operational Guide (school deployments)

For audiences where LLM output is inappropriate or PII collection is restricted —
school students in particular — set a simulation's **audience to `minors`**. This
applies a *bundle* of safe defaults across the whole stack, not a single flag
(spec §7). This guide is for UCs and school IT admins.

## Turning it on

In `company.yaml`:

```yaml
audience: minors
```

Or pick **minors** when creating the simulation. The audience is set at creation;
changing it later requires explicit confirmation.

## What the minors bundle does

| Subsystem | Safe default under `minors` |
|-----------|-----------------------------|
| Chatbots | **keyword only** — no LLM chatbots |
| Authentication | **shared password** — no individual accounts, no email collected |
| LLM-assisted content generation | **off** (must be explicitly acknowledged) |
| Multi-site | **disabled** — minors simulations are single-company |
| Messaging / inbox / group chat / 1-on-1 LLM | disabled by default |
| Task submission | text only |
| Logging | **aggregate only** — no per-student logs |
| Privacy notice | shown on **every page** of the site |
| Base library archetypes | archetypes flagged `mature` are filtered out |

The platform also forces these where it can: the config model forces keyword
chatbots, simulation creation forces shared-password auth, chatbot provisioning is
refused, and `--with-llm` generation is refused — unless you acknowledge the
specific override (below).

## Overriding a default (and why you usually shouldn't)

A default can be deviated from, but only *explicitly*, by listing the override key
in `audience_overrides`:

```yaml
audience: minors
audience_overrides:
  - llm_chatbots          # re-enable LLM chatbots (you accept the implications)
```

Override keys: `llm_chatbots`, `individual_accounts`, `llm_assist`, `messaging`,
`inbox`, `group_chat`, `conversations`, `file_upload`, `multi_site`.

When any override is active, the dashboard shows a **persistent, non-dismissible
banner** listing the non-default settings, and each acknowledgement is written to
the audit log with the UC and timestamp.

## Verifying a simulation is minors-safe

A school IT admin can confirm safety in one check:

```
GET /api/v1/simulations/{id}/audience   →   { "audience": "minors", "safe": true, "overrides": [] }
```

`safe: true` with an empty `overrides` list means no defaults have been bypassed.
The dashboard shows a green **"minors-safe — no overrides"** badge in that case.

## Important: audience mode is not a security boundary (spec §7.7)

`minors` mode reduces risk by removing risky features — it is **not** a guarantee
of perfect safety. A keyword chatbot can still answer poorly if its keyword list is
weak; an uploaded document can still contain unsuitable material. The UC remains
responsible for reviewing content. Audience mode shifts the defaults to the safer
side; it doesn't remove the duty of care.

## Operational notes

- No PII export or per-student analytics are exposed for minors simulations.
- The privacy notice is auto-generated; you don't need to add one.
- Use `examples/technova/company.yaml` as a reference minors simulation.
