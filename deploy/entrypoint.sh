#!/usr/bin/env bash
# Ensayo container entrypoint: run the FastAPI service AND Caddy.
#
# Caddy terminates :80 (gzip, friendly errors) and reverse-proxies to uvicorn on
# :8000, which serves /admin/, /api/v1/, /sims/<slug>/, /portal/, /healthz. TLS is
# terminated upstream (Cloudflare / the outer proxy), so in-container it's HTTP.
set -euo pipefail

echo "[ensayo] starting FastAPI service on :8000…"
ensayo serve --host 127.0.0.1 --port 8000 &
svc_pid=$!

# On stop, tear the service down with the container.
trap 'kill "$svc_pid" 2>/dev/null || true; wait 2>/dev/null || true' INT TERM

# Wait for the service to accept connections (max ~30s).
for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
    echo "[ensayo] service is up; starting Caddy on :80…"
    break
  fi
  sleep 1
done

# Caddy in the foreground; the script stays as PID 1 so the trap fires on stop.
caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
caddy_pid=$!
wait "$caddy_pid"
