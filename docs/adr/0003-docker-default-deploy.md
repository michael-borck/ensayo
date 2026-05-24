# ADR-0003: Docker image is the default deploy; `install.sh` is the single source of truth

**Status:** Accepted
**Source:** SPECIFICATION.md §5.4, §5.8, §15.1

## Context

The target operators range from institutional IT to a solo educator. They are not
necessarily DevOps engineers. The platform combines several runtimes — Python
3.12 (services + generator), Node 20 (Astro theme builds), and Caddy (TLS,
routing, CORS). Asking a lecturer to install and reconcile all three by hand is a
non-starter. A core promise (§5.4) is a **zero-config first run**: one command
yields a working simulation with no API keys, no DNS, and no internet beyond the
initial pull.

## Decision

- Ship a **pre-built Docker image** (published to GHCR on every push to `main`)
  bundling Python, Node, Caddy, the `ensayo` package, all themes with
  **vendored `node_modules`**, and a pre-built demo simulation.
- `docker compose up -d` is the default install path.
- **`install.sh` is the single source of truth** for setup. The Dockerfile runs
  the *same* `install.sh` during build that a bare-metal VPS user runs via
  `curl | bash`. Zero drift between the two paths.
- The image runs Caddy with **path-based fallback routing** (`/sims/<slug>/`) so
  the first run needs no DNS.

## Consequences

- **One-command demo** for evaluation; reproducible across laptop and VPS.
- **Bare-metal stays first-class** — the same script installs on a plain VPS, so
  Docker is a convenience, not a lock-in.
- **First run needs no npm/network** because theme `node_modules` are vendored in
  the image; the generator reuses them (by symlink — copying would dereference
  Astro's `.bin` shims).
- **Image is large (~1 GB)** because it carries two runtimes plus vendored deps.
  Accepted for the zero-config guarantee; can be slimmed later (multi-stage build,
  prune dev deps).
- **Node is a build-time dependency only.** It is never required to *run* a
  deployed student site (see [ADR-0004](0004-astro-theme-packages.md)).

## Alternatives considered

- **Separate install instructions per platform.** Inevitably drift; the Dockerfile
  and the docs diverge. Rejected in favour of one script.
- **No Docker, bare-metal only.** Loses the zero-config one-command demo that
  matters for getting institutional buy-in.
