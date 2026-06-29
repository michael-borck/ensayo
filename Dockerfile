# Ensayo — full-service image.
# Runs the FastAPI service (dashboard + API + generated sites) behind Caddy.
# Configure via instance.env: JWT_SECRET, EMAIL_PROVIDER/RESEND_*, ALLOWED_DOMAINS.
# First run still needs no API keys (console email + open registration), but a
# real deploy sets JWT_SECRET + an email provider + ALLOWED_DOMAINS.

FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENSAYO_DB=/var/ensayo/ensayo.db \
    WORKING_CLONES_DIR=/var/ensayo/sims

WORKDIR /opt/ensayo
COPY . /opt/ensayo

# install.sh is the single source of truth (also used for bare-metal). It
# installs deps, the ensayo package, and vendors theme node_modules (so the
# first dashboard build needs no npm). SKIP_BUILD=1 omits the static demo,
# which the service-mode container doesn't use (uvicorn serves everything).
RUN SKIP_BUILD=1 bash install.sh

# Service-mode Caddy (reverse-proxy to uvicorn) + the entrypoint that runs both.
COPY deploy/Caddyfile.service /etc/caddy/Caddyfile
COPY deploy/entrypoint.sh /opt/ensayo/entrypoint.sh
RUN chmod +x /opt/ensayo/entrypoint.sh

EXPOSE 80
CMD ["/opt/ensayo/entrypoint.sh"]
