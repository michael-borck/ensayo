# Accessibility

Ensayo targets **WCAG 2.1 AA** for the student-facing generated sites. This page
records what's in place and the known follow-ups.

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

- A formal audit with axe-core / Lighthouse across all eight themes and the
  dashboard/portal SPAs is recommended before a production rollout.
- The portal/admin SPAs are keyboard-usable but would benefit from ARIA live
  regions for async status messages.
- Per-theme contrast has been eyeballed, not instrument-verified for every
  brand-override combination.

## Testing tips

```bash
# Build a site and run an auditor against it
ensayo generate -c examples/nexuspoint/company.yaml -o ./out
npx @lhci/cli autorun --collect.staticDistDir=./out/dist   # or axe DevTools in-browser
```
