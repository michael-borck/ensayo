# Ensayo — Tier 1 zero-config image.
# Ships Python 3.12, Node 20, Caddy, the ensayo package, the tech-modern theme
# with vendored node_modules, and a pre-built demo simulation. First run needs
# no API keys, no DNS, no internet beyond the initial pull (spec §5.4).

FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WWW_ROOT=/srv/www

WORKDIR /opt/ensayo
COPY . /opt/ensayo

# install.sh is the single source of truth (also used for bare-metal).
RUN bash install.sh

EXPOSE 80
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
