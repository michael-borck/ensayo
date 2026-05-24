# ADR-0004: Themes are full Astro packages, not parameterised templates

**Status:** Accepted
**Source:** SPECIFICATION.md §3.4, §13, §15.1

## Context

The reference simulations (the six WorkReady company sites, CloudCore, etc.) each
have a **distinct visual identity** — a mining-resources site and a finance-advisory
site should not look like the same site with different colours. The generator's
output must also be **pure static HTML/CSS/JS** so it can be served by GitHub
Pages with no runtime dependency (see [ADR-0001](0001-hosting-static-pages-dynamic-api.md)).

An earlier approach used parameterised Jinja2 templates with a CSS-variable theme
system. In practice a single template tree cannot reproduce genuinely different
layouts and component structures; it collapses into "one site, recoloured".

## Decision

Each **theme is a full [Astro](https://astro.build) package** under `themes/<name>/`
with its own templates, components, scoped CSS, and `content.config.ts`. The
generator:

1. copies the chosen theme into an isolated build workspace,
2. injects the simulation's content as Astro **content collections** (employees,
   docs as files under `src/data/`; company as a JSON singleton),
3. runs `npm run build`,
4. captures the resulting `dist/`.

Themes declare a `theme.yaml` (name, supported chatbot modes/layouts/audience,
features, content props). Node is required **only at build time on the VPS**.

### Why Astro specifically

- **Zero-JS-by-default static output.** Astro ships HTML with no client runtime
  unless you opt in — ideal for GitHub Pages and fast student pages.
- **Content Collections fit the model.** The `company.yaml → site` pipeline maps
  cleanly onto typed content collections fed from generated files.
- **Component model + scoped CSS** give real per-theme identity and reuse, which
  Jinja2 lacks.
- **Islands when we need them.** Interactive bits (later phases) can hydrate
  selectively without turning the whole site into an SPA.
- **`base` support** lets one theme deploy at a domain root or a subpath
  (`/sims/<slug>/`), which multi-site and path routing both need.

## Consequences

- **Genuine visual diversity** across themes; each WorkReady site becomes a
  distinct theme package.
- **Pure static deploy** — no Node at runtime, nothing to run on GitHub Pages.
- **Build cost:** an `npm`/Astro build per generation (seconds). Mitigated by
  vendored `node_modules` and `npm ci` against committed lockfiles.
- **npm dependency management** becomes part of theme authoring: each theme commits
  `package-lock.json`; shipped themes vendor `node_modules`.
- **Theme compatibility is advisory, not enforced** — the wizard recommends
  compatible themes; overrides are logged (SPECIFICATION.md §13.7).

## Alternatives considered

- **Jinja2 + CSS variables.** Insufficient for distinct identities; rejected.
- **Next.js / Nuxt.** Heavier, SSR-oriented; more than a static-output generator
  needs, and pulls a client runtime by default.
- **Eleventy (11ty).** Capable static generator but a weaker component/typing
  story than Astro's content collections + components.
