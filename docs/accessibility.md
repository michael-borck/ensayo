# Accessibility

Ensayo targets **WCAG 2.1 AA** for the student-facing generated sites. This page
records the audit results, what's in place, and the known follow-ups.

## Audit results (2026-05)

**Automated structural audit** — [axe-core](https://github.com/dequelabs/axe-core)
4.11 run over **66 built pages** (single-company across all 6 company themes,
multi-site portal + job board + company subpages) plus the dashboard and student
portal SPAs, against the `wcag2a`/`wcag2aa`/`wcag21a`/`wcag21aa` rule sets:

> **0 violations.**

Issues found and fixed in this pass:
- `select-name` — the job-board filter `<select>`s gained `aria-label`s.
- `label` — the dashboard/portal login fields were associated via `for`/`id`; the
  wizard's dynamic employee/document rows and the portal's chat/submission inputs
  were given `aria-label`s.

**Colour contrast** — jsdom can't measure contrast, so it's checked separately
([`scripts/a11y/contrast.py`](../scripts/a11y/contrast.py)). All **18** body/muted
text-on-background pairs across the 8 themes pass AA (≥ 4.5:1); the tightest is
4.76:1.

Reproduce both: see [`scripts/a11y/README.md`](../scripts/a11y/README.md).

## In place

- **Semantic HTML & landmarks** — `<header>`, `<nav aria-label="Primary">`,
  `<main>`, `<footer>`; one `<h1>` per page with an ordered heading structure.
- **Skip link** — every company-theme page starts with a "Skip to content" link
  that jumps to `#main-content` (visible on focus).
- **Visible focus** — a global `:focus-visible` outline (theme accent) so keyboard
  users can see where they are.
- **Language** — `<html lang="en">`.
- **Responsive** — `<meta viewport>`; layouts reflow to a single column on small
  screens; text is not in images.
- **Forms** — the keyword chatbot input has an `aria-label`; the dashboard and
  portal use real `<label>`s and native controls.
- **Government theme** — the `government-formal` theme adds extra-strong focus
  outlines suited to public-sector accessibility expectations.

## Authoring responsibilities (content)

Automated structure can't guarantee accessible *content*. UCs should:

- Provide meaningful link text and document titles.
- Keep colour contrast in `branding.colors` adequate against the theme background
  (themes ship AA-compliant defaults; custom brand colours are the UC's to check).
- Write alt text for any images they add.

## Known follow-ups

- **In-browser pass** for JS-rendered states (the dashboard/portal *after* login)
  and real zoom/contrast behaviour — run axe DevTools or Lighthouse against a live
  `ensayo serve`. The automated audit above runs over static HTML and so does not
  exercise post-login dynamic views (those controls have been hardened with
  `aria-label`s, but haven't been instrument-verified live).
- The portal/admin SPAs would benefit from ARIA **live regions** for async status
  messages.
- Contrast is verified for theme defaults; **custom brand-colour overrides** in a
  `company.yaml` are the UC's responsibility to check.

## Testing tips

Reproduce the audit with [`scripts/a11y/`](../scripts/a11y/README.md):

```bash
python3 scripts/a11y/contrast.py            # theme contrast (no deps)
# structural: build sites, then `node scripts/a11y/audit.mjs <html files>`
# in-browser: ensayo serve, then axe DevTools / Lighthouse on /admin/ and /portal/
```
