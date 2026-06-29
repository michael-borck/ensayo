#!/usr/bin/env bash
#
# Ensayo — local setup.
#
# Run this from inside your ensayo checkout (you clone the repo wherever you
# like first). It installs the local environment and configures it — nothing
# more (no serving, no proxy, no systemd). You run it yourself afterwards:
#
#   - installs uv (brings its own Python) + Node 20
#   - `uv sync` (Python deps) + vendors theme node_modules
#   - writes .env (generates JWT_SECRET; prompts for the rest)
#   - creates the instance admin
#
# Then it prints how to start the service. Reverse proxy / TLS (Caddy,
# Cloudflare, …) and process management are yours to set up.
#
#   bash deploy/selfhost.sh                                     # interactive
#   NONINTERACTIVE=1 ENSAYO_ADMIN_EMAIL=you@edu ENSAYO_ADMIN_PASSWORD=... \
#     RESEND_API_KEY=re_... RESEND_FROM="..." ALLOWED_DOMAINS=edu \
#     bash deploy/selfhost.sh                                   # automation
#
set -euo pipefail

HTTP_PORT="${ENSAYO_HTTP_PORT:-8000}"
HOST="${ENSAYO_HOST:-127.0.0.1}"   # referenced only in the printed "how to run" hint

log()  { printf '\033[36m[ensayo]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[ensayo]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[ensayo] error:\033[0m %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
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
# Resolve a setting: existing .env value → env var → interactive prompt (or default).
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

SUDO=""; [ "$(id -u)" -ne 0 ] && have sudo && SUDO="sudo"

# --- 0. locate the repo (walk up to pyproject.toml name="ensayo") ----------
root=""
d="$(pwd)"
while [ "$d" != "/" ]; do
  if [ -f "$d/pyproject.toml" ] && grep -q 'name = "ensayo"' "$d/pyproject.toml" 2>/dev/null; then
    root="$d"; break
  fi
  d="$(dirname "$d")"
done
[ -n "$root" ] || die "run this from inside your ensayo checkout (no pyproject.toml with name=\"ensayo\" found upward)."
cd "$root"
log "Repo: $root"

# --- 1. system packages (Debian/Ubuntu; usually already present) -----------
if is_debian; then
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

# --- 4. Python deps --------------------------------------------------------
log "Installing Python deps (uv sync)…"
uv sync --quiet

# --- 5. vendor theme node_modules (so the first build is fast) -------------
log "Vendoring theme dependencies…"
for t in themes/*/; do
  [ -f "$t/package.json" ] || continue
  (cd "$t" && npm install --no-audit --no-fund >/dev/null 2>&1 || true)
done

# --- 6. .env ---------------------------------------------------------------
[ -f .env ] || cp .env.example .env
JWT="$(uv run python -c 'import secrets; print(secrets.token_urlsafe(32))' 2>/dev/null || openssl rand -hex 32)"
set_env JWT_SECRET "$JWT"
ask RESEND_API_KEY  "Resend API key (blank = no email; codes show in the admin panel)" ""
ask RESEND_FROM     "Resend From address" "Ensayo <noreply@contact.locoensayo.org>"
ask ALLOWED_DOMAINS "Allowed sign-up domains (comma-sep; blank = open)" "curtin.edu.au"
if grep -qE '^RESEND_API_KEY=re_' .env; then set_env EMAIL_PROVIDER resend; fi

# --- 7. instance admin -----------------------------------------------------
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

# --- done ------------------------------------------------------------------
echo
log "Setup complete."
echo "  Start the service:    uv run ensayo serve        # → http://$HOST:$HTTP_PORT/admin/"
echo "  Test email delivery:  uv run ensayo admin send-test-email --to you@your.edu"
echo "  Logs / stop:          the service runs in that terminal; Ctrl+C stops it."
echo "  Next: put your reverse proxy (Caddy/Cloudflare) in front, served at the domain root."
