# Accessibility audit scripts

Reproduce the WCAG 2.1 AA audit summarised in [`docs/accessibility.md`](../../docs/accessibility.md).

## Structural audit (axe-core)

Runs axe-core over built HTML via jsdom (no browser needed). Colour-contrast is
disabled here (jsdom has no layout engine — see the contrast check below).

```bash
# 1. Build representative sites
ensayo generate -c examples/nexuspoint/company.yaml -o /tmp/aa/company
ensayo generate -c examples/workready-mini/simulation.yaml -o /tmp/aa/multi

# 2. Install the audit deps (one-off) and run
cd scripts/a11y && npm init -y >/dev/null && npm install jsdom axe-core
node audit.mjs $(find /tmp/aa -name '*.html') \
  ../../src/ensayo/api/static/admin/index.html \
  ../../src/ensayo/api/static/portal/index.html
```

Exit code is non-zero if any WCAG 2.1 A/AA violations are found.

## Contrast check (no deps)

```bash
python3 scripts/a11y/contrast.py     # from the repo root
```

Checks body/muted text against backgrounds for every theme; non-zero exit if any
normal-text pair is below 4.5:1.

## In-browser (recommended before a production rollout)

For JS-rendered states (the dashboard/portal after login) and real contrast/zoom
checks, run axe DevTools or Lighthouse against a live `ensayo serve`.
