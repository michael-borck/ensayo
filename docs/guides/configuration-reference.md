# Configuration Reference

Two config formats: **`company.yaml`** (a single-company simulation) and
**`simulation.yaml`** (a multi-site simulation — a portal plus several companies).
`ensayo generate` auto-detects multi-site by the presence of a `companies:` key.
Unknown keys are ignored, so configs are forward-compatible.

---

## company.yaml

### Top-level

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `company` | mapping | — | **Required.** See [company](#company) below. |
| `audience` | `adults` \| `minors` | `adults` | `minors` applies the safe-mode bundle (see [Safe Mode](safe-mode.md)). |
| `theme` | string | `tech-modern` | A theme under `themes/` (run `ensayo list`). |
| `layout` | string | `topnav` | Advisory; theme-dependent. |
| `chatbot_mode` | `keyword` \| `llm` \| `hybrid` | `keyword` | Default for all employees. `minors` forces `keyword`. |
| `api_base_url` | string | `""` | VPS API origin for cross-origin calls from GitHub Pages. `""` = same origin. |
| `audience_overrides` | list[string] | `[]` | Acknowledged minors-safe deviations (see [Safe Mode](safe-mode.md)). |
| `branding` | mapping | — | `colors: {primary, secondary, accent}`, `logo`, `font`. |
| `platform` | mapping | — | `booking_enabled`, `lecturer_dashboard`, `chatbot_requires_booking`. |
| `anythingllm` | mapping | — | `base_url`, `embed_src` (set by Phase 4 provisioning). |
| `llm` | mapping | — | Per-sim LLM: `provider`, `model`, `base_url`, `api_key_env`. |
| `employees` | list | `[]` | See [employee](#employee). |
| `documents` | list | `[]` | See [document](#document). |
| `jobs` | list | `[]` | See [job](#job) (used by multi-site job board). |

### company

| Key | Type | Notes |
|-----|------|-------|
| `name` | string | **Required.** |
| `slug` | string | Auto-derived from `name` if omitted. |
| `tagline` | string | |
| `industry` | string | Matches an industry in the library (e.g. `cloud_services`, `finance`, `mining`, `government`, `nonprofit`, `consulting`, `software_development`, `general`). |
| `location` | string | |
| `profile` | mapping | `founded`, `employees`, `revenue`, `structure`, `description`, `key_facts` (list), `services` (list). |
| `scenario` | mapping | `type` (e.g. `growth`, `breach`, `digital_transformation`, `crisis`, `merger`), `name`, `description`, `key_tensions` (list). |

### employee

| Key | Type | Notes |
|-----|------|-------|
| `name` | string | **Required.** |
| `id` / `slug` | string | Auto-derived from `name`. |
| `role` | string | |
| `title` | string | Optional honorific. |
| `archetype` | string | A role archetype (run a build to see; e.g. `founder_ceo`, `operations_manager`, `technical_specialist`, `finance_manager`, `hr_manager`, `sales_lead`, `marketing_manager`, `project_manager`, `customer_support`, `executive_assistant`, `staff`). Seeds personality/knowledge/voice. |
| `tier` | `executive` \| `manager` \| `specialist` \| `staff` | |
| `department` | string | |
| `chatbot_mode` | `keyword` \| `llm` \| `hybrid` | Overrides the company default. |
| `refers_to` | mapping | `{topic: "Colleague Name"}` cross-referral map. |
| `customisation` | mapping | `years_at_company`, `years_in_industry`, `background`, `prior_experience` (list), `personality_additions` (list), `knowledge_additions` (list), `opinions` (list), `scenario_perspective`. Empty fields can be filled by `--with-llm`. |

### document

| Key | Type | Notes |
|-----|------|-------|
| `type` | string | `policy`, `support`, `internal`, `press`, `custom` (drives the template). |
| `title` | string | **Required.** |
| `brief` | string | One-line summary; the seed for LLM/stub generation. |
| `content` | string | Full Markdown body. If empty, `--with-llm` generates it. |

### job

| Key | Type | Notes |
|-----|------|-------|
| `title` | string | **Required.** |
| `department`, `employment_type`, `reports_to`, `brief` | string | Shown on the multi-site job board. |

---

## simulation.yaml (multi-site)

| Key | Type | Notes |
|-----|------|-------|
| `name` | string | **Required.** |
| `slug` | string | Auto-derived from `name`. |
| `type` | string | `multi_site`. |
| `audience` | `adults` | Multi-site is **not** available for `minors` (spec §7.5). |
| `workflow` | string | A bundled workflow name (`internship`, `medical_network`). Drives the student lifecycle. |
| `theme` | string | Portal theme (default `portal-clean`). |
| `branding` | mapping | Portal branding. |
| `portal` | mapping | `title`, `tagline`, `description`. |
| `companies` | list | **Required, non-empty.** Each entry is a full `company.yaml` body (the `company:` mapping plus `theme`, `branding`, `employees`, `documents`, `jobs`). Company slugs must be unique. |

Each company is generated at the subpath `/<company-slug>/`; the portal is built at
the root and the job board at `/jobs/`.

See `examples/nexuspoint/company.yaml`, `examples/sparse/company.yaml`,
`examples/technova/company.yaml` (minors), and
`examples/workready-mini/simulation.yaml` (multi-site).
