# Getting Started

This guide takes a Unit Coordinator (UC) from nothing to a running simulation that
students can use. It assumes the instance is already deployed (see the
[Deployment Guide](deployment.md)); if you're evaluating locally, the
[zero-config first run](deployment.md#zero-config-first-run) gets you a server in
one command.

## 1. Sign in to the dashboard

Open the dashboard at `https://<your-instance>/admin/` (locally:
`http://localhost:8000/admin/`). Sign in with the UC account your instance admin
created for you. (Admins create accounts with
`ensayo admin create-uc --email you@uni.edu`.)

## 2. Create a simulation

Click **+ New simulation**. You'll provide:

- **Name** — e.g. *"CloudCore Networks — ISYS6018 Sem 1 2026"*.
- **Student authentication** — pick one:
  - *Shared password* — one password for the whole class, no student data collected.
  - *Individual accounts* — each student registers with email + password.
  - *Email only* — students sign in with just an email.
- **company.yaml** — the simulation's content. Start from the pre-filled template
  and edit it, or paste your own. The full schema is in the
  [Configuration Reference](configuration-reference.md).
- **Generate content with LLM** (optional) — if a provider is configured, this
  writes the employee backstories, documents, and scenario for you. Leave it off
  to use exactly what you wrote (or stub drafts).

Click **Create**. The server validates your config, generates the site into a git
working clone, and lists it.

> **Tip — start sparse.** You can give just names, roles, and `archetype`s for each
> employee and a scenario `type`, then tick *Generate content with LLM*. See
> `examples/sparse/company.yaml`.

## 3. Edit and iterate

Use **Edit** on a simulation to change its `company.yaml`. **Save** writes your
changes and regenerates the site locally but does **not** show them to students —
so you can iterate mid-semester safely. When you're happy, **Publish**.

## 4. Publish to GitHub Pages

Click **Publish**. The first time, you'll be asked for a GitHub repo URL (the
instance needs a `GITHUB_TOKEN` configured). Ensayo pushes the content to `main`
and the built site to the `gh-pages` branch, and the simulation goes live at your
GitHub Pages URL.

## 5. Add students

In the **Students** panel you can:

- Upload a **class list** (CSV of emails) to restrict who can register.
- See the roster, per-student activity, and booking counts.
- Reset a password or remove a student (PII is redacted on removal).
- Export the roster as CSV.

With *shared password*, just give students the password.

## 6. (Optional) LLM chatbots

Click **Provision chatbots** to create an AnythingLLM workspace per employee
(RAG-grounded chat). Without an AnythingLLM instance this runs in dry-run mode.
Employees stay on the deterministic keyword chatbot until provisioned. See the
[Deployment Guide](deployment.md#anythingllm) for AnythingLLM setup.

## 7. Students use it

Students open the published site. They chat with employees, read documents, and —
in multi-site simulations — sign in to the **student portal** (`/portal/`) to apply,
work through the scenario's stages, hold interviews, submit work, and complete
their journey.

## Teaching to school students?

Set the audience to **minors** when creating the simulation. This applies a bundle
of safe defaults (keyword chatbots only, shared-password auth, no messaging, a
privacy notice on every page). See the [Safe Mode Guide](safe-mode.md).

## Next steps

- [Configuration Reference](configuration-reference.md) — every `company.yaml` /
  `simulation.yaml` field.
- [Theme Authoring](theme-authoring.md) — build a new visual identity.
- [Archetype Authoring](archetype-authoring.md) — add role templates.
