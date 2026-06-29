#!/usr/bin/env bash
#
# Ensayo self-host setup — one command to a running full service on a fresh VPS.
#
#   curl -fsSL https://raw.githubusercontent.com/michael-borck/ensayo/main/deploy/selfhost.sh | bash
#
#   # or, after cloning:
#   bash deploy/selfhost.sh
#
# Installs uv (brings its own Python) + Node 20, clones (or reuses the current
# checkout), `uv sync`s, vendors theme deps, writes .env (generates JWT_SECRET,
# prompts for the rest), creates the instance admin, installs a systemd unit, and
# — if you give a domain — Caddy as a reverse proxy. Idempotent; safe to re-run.
#
# Non-interactive (automation): export ENSAYO_DOMAIN, ENSAYO_ADMIN_EMAIL,
# ENSAYO_ADMIN_PASSWORD, RESEND_API_KEY, RESEND_FROM, ALLOWED_DOMAINS, and set
# NONINTERACTIVE=1 before running.
#
set -euo pipefail

ENSAYO_HOME="${ENSAYO_HOME:-/opt/ensayo}"
HTTP_PORT="${ENSAYO_HTTP_PORT:-8000}"
RUN_USER="${RUN_USER:-root}"

log()  { printf '\033[36m[ensayo]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[ensayo]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[ensayo] error:\033[0m %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

SUDO=""; [ "$(id -u)" -ne 0 ] && have sudo && SUDO="sudo"
is_debian() { [ -f /etc/debian_version ] || have apt-get; }

# Ensure an uncommented KEY=VALUE line in .env (uncomment if commented, else add).
set_env() {
  local k="$1" v="$2"
  if grep -qE "^$k=" .env; then
    sed -i.bak "s|^$k=.*|$k=$v|" .env && rm -f .env.bak
  elif grep -qE "^#[[:space:]]*$k=" .env; then
    sed -i.bak "s|^#[[:space:]]*$k=.*|$k=$v|" .env && rm -f .env.bak
  else
    printf '%s=%s\n' "$k" "$v" >> .env
  fi
}

# Read a setting: existing .env value → env var → interactive prompt (or default).
ask() {  # ask VAR "label" "default"
  local var="$1" label="$2" def="${3:-}" cur ans
  cur=$(grep -E "^$var=" .env 2>/dev/null | head -1 | cut -d= -f2- || true)
  [ -n "${!var:-}" ] && cur="${!var}"
  if [ -z "$cur" ] && [ -z "${NONINTERACTIVE:-}" ]; then
    printf '[ensayo] %s%s: ' "$label" "${def:+ [$def]}" >&2
    read -r ans </dev/tty >&2 || ans=""
    cur="${ans:-$def}"
  fi
  [ -n "$cur" ] && set_env "$var" "$cur"
}

# --- 1. system packages ----------------------------------------------------
if is_debian; then
  log "Installing system packages…"
  $SUDO apt-get update -qq
  $SUDO apt-get install -y --no-install-recommends git curl ca-certificates gnupg >/dev/null
fi

# --- 2. uv (manages Python + the venv; fetches Python 3.12 itself) ---------
export PATH="$HOME/.local/bin:$PATH"
if ! have uv; then
  log "Installing uv…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
have uv || die "uv install failed."

# --- 3. Node 20 (uv can't install Node; needed to build sims) --------------
node_ok() { have node && [ "$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)" -ge 20 ]; }
if ! node_ok; then
  if is_debian; then
    log "Installing Node 20…"
    curl -fsSL https://deb.nodesource.com/setup_20.x | $SUDO bash - >/dev/null
    $SUDO apt-get install -y --no-install-recommends nodejs >/dev/null
  else
    warn "Node 20+ not found and this isn't Debian/Ubuntu — install Node 20 manually (required to build sims)."
  fi
fi

# --- 4. get the code -------------------------------------------------------
if [ -f pyproject.toml ] && grep -q 'name = "ensayo"' pyproject.toml 2>/dev/null; then
  ENSAYO_HOME="$(pwd)"; log "Using current checkout: $ENSAYO_HOME"
else
  if [ ! -d "$ENSAYO_HOME/.git" ]; then
    log "Cloning ensayo → $ENSAYO_HOME"
    $SUDO mkdir -p "$ENSAYO_HOME"
    $SUDO git clone https://github.com/michael-borck/ensayo.git "$ENSAYO_HOME"
  fi
  cd "$ENSAYO_HOME"
fi

# --- 5. Python deps (uv fetches Python 3.12 itself) ------------------------
log "Installing Python deps (uv sync)…"
uv sync --quiet

# --- 6. vendor theme node_modules (first dashboard build then needs no npm) -
log "Vendoring theme dependencies…"
for t in themes/*/; do
  [ -f "$t/package.json" ] || continue
  (cd "$t" && npm install --no-audit --no-fund >/dev/null 2>&1 || true)
done

# --- 7. .env ---------------------------------------------------------------
[ -f .env ] || cp .env.example .env
JWT="$(uv run python -c 'import secrets; print(secrets.token_urlsafe(32))' 2>/dev/null || openssl rand -hex 32)"
set_env JWT_SECRET "$JWT"
ask RESEND_API_KEY  "Resend API key (blank = no email; codes show in admin panel)" ""
ask RESEND_FROM     "Resend From address" "Ensayo <noreply@contact.locoensayo.org>"
ask ALLOWED_DOMAINS "Allowed sign-up domains (comma-sep; blank = open)" "curtin.edu.au"
ask ENSAYO_DOMAIN   "Public domain for Caddy (blank = skip Caddy, you proxy yourself)" ""
# If a real Resend key was supplied, force the provider to resend.
if grep -qE '^RESEND_API_KEY=re_' .env; then set_env EMAIL_PROVIDER resend; fi

# --- 8. instance admin -----------------------------------------------------
ADMIN_EMAIL="${ENSAYO_ADMIN_EMAIL:-}"
if [ -z "$ADMIN_EMAIL" ] && [ -z "${NONINTERACTIVE:-}" ]; then
  printf '[ensayo] Admin email (blank = skip): ' >&2
  read -r ADMIN_EMAIL </dev/tty >&2 || ADMIN_EMAIL=""
fi
if [ -n "$ADMIN_EMAIL" ]; then
  ADMIN_PW="${ENSAYO_ADMIN_PASSWORD:-}"
  if [ -z "$ADMIN_PW" ]; then
    ADMIN_PW="$(uv run python -c 'import secrets,string; print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(18)))')"
    log "Generated admin password (save it now): $ADMIN_PW"
  fi
  log "Creating instance admin: $ADMIN_EMAIL"
  uv run ensayo admin create-uc -e "$ADMIN_EMAIL" -p "$ADMIN_PW" --admin 2>/dev/null \
    || warn "(admin may already exist; continuing)"
fi

# --- 9. systemd unit (keep it running across reboots) ----------------------
if is_debian; then
  UV_BIN="$(command -v uv)"
  log "Installing systemd unit…"
  $SUDO tee /etc/systemd/system/ensayo.service >/dev/null <<UNIT
[Unit]
Description=Ensayo (dashboard + API)
After=network.target

[Service]
Type=simple
WorkingDirectory=$ENSAYO_HOME
EnvironmentFile=$ENSAYO_HOME/.env
ExecStart=$UV_BIN run ensayo serve --host 127.0.0.1 --port $HTTP_PORT
Restart=always
User=$RUN_USER

[Install]
WantedBy=multi-user.target
UNIT
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable --now ensayo
  log "Started: systemctl status ensayo"
else
  warn "Not Debian/Ubuntu — skipping systemd. Run manually: uv run ensayo serve"
fi

# --- 10. (optional) Caddy reverse proxy if a domain was given --------------
DOMAIN="$(grep -E '^ENSAYO_DOMAIN=' .env 2>/dev/null | head -1 | cut -d= -f2- || true)"
if [ -n "$DOMAIN" ] && is_debian; then
  if ! have caddy; then
    log "Installing Caddy…"
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
      | $SUDO gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>/dev/null || true
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
      | $SUDO tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
    $SUDO apt-get update -qq && $SUDO apt-get install -y caddy >/dev/null
  fi
  log "Caddy reverse-proxy: $DOMAIN → 127.0.0.1:$HTTP_PORT"
  $SUDO tee /etc/caddy/Caddyfile >/dev/null <<CADDY
$DOMAIN {
    reverse_proxy 127.0.0.1:$HTTP_PORT
}
CADDY
  $SUDO systemctl reload caddy 2>/dev/null || $SUDO systemctl restart caddy 2>/dev/null || true
fi

# --- done ------------------------------------------------------------------
echo
log "Done."
if [ -n "$DOMAIN" ]; then
  echo "  Dashboard:  https://$DOMAIN/admin/   (point Cloudflare DNS at this box)"
else
  echo "  Dashboard:  http://127.0.0.1:$HTTP_PORT/admin/   (put a proxy + Cloudflare in front)"
fi
echo "  Test email: uv run ensayo admin send-test-email --to you@your.edu"
echo "  Logs:       journalctl -u ensayo -f   (or 'uv run ensayo serve' if no systemd)"
