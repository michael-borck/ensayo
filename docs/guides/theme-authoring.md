# Theme Authoring Guide

A theme is a full [Astro](https://astro.build) package under `themes/<name>/`
([ADR-0004](../adr/0004-astro-theme-packages.md)). The generator copies it into a
build workspace, injects the simulation's content, runs `npm run build`, and
captures the static `dist/`. Node is build-time only; deployed sites are pure
static HTML.

## The fastest path: copy and restyle

All company themes share one **data contract**, so the quickest way to a new theme
is to copy `tech-modern` and change the visual layer:

```bash
cd themes
rsync -a --exclude node_modules --exclude dist --exclude .astro tech-modern/ my-theme/
cd my-theme && npm install        # vendor deps + create package-lock.json
# edit theme.yaml, package.json "name", and src/styles/theme.css
```

Then `ensayo list` shows it and `ensayo generate -c company.yaml --theme my-theme`
builds it.

## Anatomy

```
themes/my-theme/
├── theme.yaml              # name, description, supports, features, content_props
├── package.json           # "astro": "^5" ; commit package-lock.json
├── astro.config.mjs        # base from process.env.ENSAYO_BASE
├── src/
│   ├── content.config.ts   # employees (JSON glob) + docs (md glob) collections
│   ├── data/               # committed FIXTURES (overwritten by the generator)
│   ├── layouts/Base.astro  # shell; injects branding + ENSAYO_API_BASE/SLUG globals
│   ├── components/EmployeeCard.astro
│   ├── pages/index, staff/index, staff/[slug], docs/index, docs/[slug]
│   └── styles/theme.css    # the visual identity (the part you change)
└── public/ensayo/          # dev copy of shared client scripts
```

## The data contract (don't break this)

The generator writes the simulation's content into the theme's `src/data/`:

- `company.json` — imported directly for company info, branding, scenario.
- `employees/<slug>.json` — one per employee (consumed by the `employees`
  collection); includes `keywords` (keyword-chatbot data) and chatbot fields.
- `docs/<slug>.md` — Markdown documents (the `docs` collection).

Your pages must read these via the same field names. Keep `src/content.config.ts`
compatible (copy it from `tech-modern`). The **CSS class names** (`.site-header`,
`.hero`, `.emp-grid`, `.emp-card`, `.panel`, `.doc-list`, `.ensayo-chat`, …) form a
contract too — restyle them, don't rename them.

### Chatbot wiring (keep as-is)

The employee page mounts the deterministic keyword chatbot via
`<div data-ensayo-chat>` + a `ensayo-kw-data` JSON script + `/ensayo/keyword-chatbot.js`,
and renders an AnythingLLM embed when an employee has been provisioned. Booking
gating uses `data-ensayo-chat-wrap` + `/ensayo/booking-gate.js`. The generator
deploys those shared scripts automatically.

### Base path

A site can deploy at a domain root or under `/sims/<slug>/` (multi-site). Always
build links with `import.meta.env.BASE_URL`; `astro.config.mjs` reads
`process.env.ENSAYO_BASE`.

## Branding vs theme

`theme.css` defines the *identity* (palette, fonts, shape) via CSS variables incl.
`--bg`, `--surface`, `--text`, `--font`, and accepts per-simulation brand overrides
through `--brand-primary` / `--brand-secondary` / `--brand-accent` (injected by
`Base.astro` from the config's `branding.colors`). A theme should look coherent
with *and* without brand overrides.

## theme.yaml

```yaml
name: my-theme
description: One line describing the look and intended sector.
derived_from: some-reference-site        # optional
supports:
  chatbot_modes: [keyword, llm, hybrid]
  layouts: [topnav, sidebar]
  audience: [adults, minors]
features: [employee_directory, document_library, keyword_chatbot]
content_props: [company, employees, documents]
```

`supports` is **advisory** ([§13.7](../SPECIFICATION.md)) — overrides are logged,
not blocked, and signal where to extend a theme.

## Checklist

- [ ] `theme.yaml` + unique `package.json` name; `package-lock.json` committed.
- [ ] Builds: `cd themes/my-theme && npm run dev` with the fixtures.
- [ ] Generates: `ensayo generate -c examples/nexuspoint/company.yaml --theme my-theme`.
- [ ] Chatbot, docs, and base-path links all work in the built `dist/`.
