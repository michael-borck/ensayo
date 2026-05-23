#!/usr/bin/env bash
#
# Ensayo installer — the single source of truth for bare-metal and Docker
# (spec §5.8). The Dockerfile runs this exact script during build; bare-metal
# users curl|bash the same one. Zero drift between paths.
#
# Idempotent: safe to re-run. Honours:
#   SKIP_DEPS=1   skip system package installation
#   SKIP_BUILD=1  skip building the demo simulation
#   WWW_ROOT=...  where built sites are served from (default /srv/www)
#
set -euo pipefail

ENSAYO_HOME="${ENSAYO_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
WWW_ROOT="${WWW_ROOT:-/srv/www}"
SUDO=""
[ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

log() { printf '\033[36m[ensayo]\033[0m %s\n' "$*"; }

install_deps() {
  if [ "${SKIP_DEPS:-0}" = "1" ]; then log "SKIP_DEPS=1 — skipping system deps"; return; fi
  log "Installing system dependencies (node 20, caddy, python, git)…"
  export DEBIAN_FRONTEND=noninteractive
  $SUDO apt-get update
  $SUDO apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg git python3 python3-pip python3-venv \
    debian-keyring debian-archive-keyring apt-transport-https

  if ! command -v node >/dev/null 2>&1; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | $SUDO bash -
    $SUDO apt-get install -y --no-install-recommends nodejs
  fi

  if ! command -v caddy >/dev/null 2>&1; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
      | $SUDO gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
      | $SUDO tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
    $SUDO apt-get update && $SUDO apt-get install -y caddy
  fi
  $SUDO rm -rf /var/lib/apt/lists/* || true
}

install_ensayo() {
  log "Installing the ensayo Python package…"
  pip3 install --no-cache-dir --break-system-packages -e "$ENSAYO_HOME" 2>/dev/null \
    || pip3 install --no-cache-dir -e "$ENSAYO_HOME"

  log "Vendoring theme dependencies (so first run needs no npm network)…"
  ( cd "$ENSAYO_HOME/themes/tech-modern" && npm install --no-audit --no-fund )
}

build_demo() {
  if [ "${SKIP_BUILD:-0}" = "1" ]; then log "SKIP_BUILD=1 — skipping demo build"; return; fi
  log "Building the demo simulation (NexusPoint Systems)…"
  tmp="$(mktemp -d)"
  ensayo generate \
    -c "$ENSAYO_HOME/examples/nexuspoint/company.yaml" \
    -o "$tmp/demo" --base /sims/nexuspoint/
  $SUDO mkdir -p "$WWW_ROOT/sims/nexuspoint"
  $SUDO cp -r "$tmp/demo/dist/." "$WWW_ROOT/sims/nexuspoint/"
  $SUDO cp "$ENSAYO_HOME/deploy/sims-index.html" "$WWW_ROOT/index.html"
  rm -rf "$tmp"

  $SUDO mkdir -p /etc/caddy
  $SUDO cp "$ENSAYO_HOME/deploy/Caddyfile" /etc/caddy/Caddyfile
}

install_deps
install_ensayo
build_demo

log "Done."
log "Serve with: caddy run --config /etc/caddy/Caddyfile --adapter caddyfile"
log "Then open:  http://localhost/  (or the mapped port in docker-compose)"
