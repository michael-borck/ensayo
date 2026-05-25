# Archetype Authoring Guide

A **role archetype** is a reusable template that seeds an employee's persona — their
default traits, knowledge, voice, role framing, and keyword-chatbot responses. The
layered prompt builder composes a persona as **archetype → industry → company →
individual** (the individual's `customisation` overrides/extends the archetype).

Archetypes ship as YAML under `src/ensayo/library/archetypes/`. The ten bundled
roles cover `founder_ceo`, `operations_manager`, `technical_specialist`,
`finance_manager`, `hr_manager`, `sales_lead`, `marketing_manager`,
`project_manager`, `customer_support`, `executive_assistant`, plus the generic
`staff` fallback used when an `archetype:` doesn't match.

## Add one

Create `src/ensayo/library/archetypes/<name>.yaml`:

```yaml
name: legal_counsel
label: "Legal Counsel"
default_tier: manager
communication_style: "Precise and cautious; flags risk and qualifies advice."
personality:
  - "Risk-aware and detail-oriented"
  - "Calm under pressure"
knowledge:
  - "Contracts and compliance"
  - "Regulatory obligations"
prompt_fragment: >
  You advise the business on legal and compliance matters. You're careful to
  distinguish what's settled from what needs external counsel.
keyword_seeds:
  - keywords: ["legal", "contract", "compliance", "risk"]
    response: "Happy to talk through the legal angle — though for anything binding we'd get external counsel."
referral_topics: ["legal", "compliance", "contracts"]
mature: false   # set true to hide this archetype from minors-audience simulations
```

Reference it from a `company.yaml` employee:

```yaml
employees:
  - name: "Dana Cho"
    role: "General Counsel"
    archetype: legal_counsel
```

## Fields

| Field | Purpose |
|-------|---------|
| `name` | Identifier used in `archetype:` (the file stem should match). |
| `label` | Human-readable role name. |
| `default_tier` | `executive` / `manager` / `specialist` / `staff`. |
| `communication_style` | One sentence shaping the chatbot's voice (added to the system prompt). |
| `personality`, `knowledge` | Baseline lists, merged with the individual's `*_additions` (deduplicated, order-preserving). |
| `prompt_fragment` | A short paragraph framing the role, added as "YOUR ROLE" in the prompt. |
| `keyword_seeds` | `{keywords: [...], response: "..."}` entries seeding the deterministic keyword chatbot. |
| `referral_topics` | Topics this role naturally owns. |
| `mature` | `true` filters the archetype out of `minors` simulations ([Safe Mode](safe-mode.md)). |

## How it's used

- **Prompt** (`content/employees/<slug>-prompt.txt`) — the canonical persona, built
  by layering archetype + industry + company + individual.
- **Keyword chatbot** — `keyword_seeds` give role-appropriate answers out of the
  box, before any individual customisation.
- **LLM generation** — `--with-llm` uses the role + company context to write
  backstories/opinions; the archetype keeps un-customised employees coherent.

## Tip

Write archetypes in neutral phrasing that reads correctly under both "WHAT YOU
KNOW:" (the prompt) and a profile page — avoid third-person "their".
