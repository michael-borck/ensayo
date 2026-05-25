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

Click **+ New simulation** to open the **guided wizard** — you never have to write
YAML. It steps through:

1. **Basics** — simulation name, audience (adults/minors), student sign-in
   (shared password / individual accounts / email only), theme, and an optional
   **workflow** (e.g. `internship`) that drives the student's stage-by-stage journey.
2. **Company** — name, industry, location, description.
3. **Scenario** — the central challenge (pick a type; name + description optional).
4. **People** — add the employees students can interview (name, role, archetype).
5. **Documents** — policies/guides (type, title, brief).
6. **Finish** — tick *Generate content with LLM* (writes backstories/docs/scenario
   if a provider is configured) and *Build the site*, then **Create**.

The wizard sends your answers to the server, which builds and validates the
`company.yaml`, generates the site into a git working clone, and lists it. Leave
optional fields blank and tick *Generate content with LLM* to let the engine fill
them in.

> **Prefer YAML?** Click **Advanced: paste YAML** in the wizard to edit the raw
> `company.yaml` directly (full schema in the
> [Configuration Reference](configuration-reference.md)).

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
