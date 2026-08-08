#!/usr/bin/env bash
# vision-one-mcp-python: bootstrap Docker + the Compose plugin on a fresh Ubuntu box.
#
# Usable as EC2 user-data on launch, or by running it manually over SSH on any Ubuntu
# 22.04+ host -- cloud or on-prem. Nothing here is AWS-specific; this is exactly what
# you'd hand a customer running their own machine, minus the EC2 launch step itself.
set -euo pipefail

log() { echo "[bootstrap] $*"; }

log "Installing Docker Engine + Compose plugin..."
curl -fsSL https://get.docker.com | sh -

TARGET_USER="${SUDO_USER:-${USER}}"
usermod -aG docker "${TARGET_USER}" || true

log "Done. Log out/in (or start a new SSH session) for the docker group change to take effect."
log ""
log "Next steps:"
log "  1. Point DNS for your chosen hostname at this box's public/elastic IP."
log "  2. cp .env.example .env  &&  edit it (API key, bearer token, CADDY_DOMAIN, CADDY_EMAIL)"
log "  3. docker compose up -d --build"
log "  4. curl https://\$CADDY_DOMAIN/healthz"
