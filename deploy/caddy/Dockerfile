# syntax=docker/dockerfile:1.4
# =============================================================================
# Caddy reverse proxy for the split-services Compose stacks
# (root docker-compose.yaml and docker-compose.yml).
#
# The official caddy image is rebuilt on its own cadence and lags behind Go
# security releases (2.11.4 still ships a Go 1.26.5 stdlib, flagged for
# CVE-2026-39821 and friends). Building the same pinned Caddy release here lets
# the Go toolchain be bumped independently of upstream image rebuilds.
# GOTOOLCHAIN=local keeps the build on GO_VERSION instead of letting go.mod pull
# a different toolchain down.
#
# Keep CADDY_VERSION and GO_VERSION in sync with deploy/all-in-one/Dockerfile.
# =============================================================================
ARG CADDY_VERSION=2.11.4
ARG GO_VERSION=1.26.7

FROM golang:${GO_VERSION} AS caddy_builder
ARG CADDY_VERSION
ENV CGO_ENABLED=0 \
    GOTOOLCHAIN=local \
    GOBIN=/usr/bin
RUN go install "github.com/caddyserver/caddy/v2/cmd/caddy@v${CADDY_VERSION}" && \
    caddy version

# =============================================================================
# Runtime. Ubuntu 26.04 LTS, matching the other images in this repo. Only
# ca-certificates is needed (ACME/TLS); the Caddy binary is static.
# =============================================================================
FROM ubuntu:26.04

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Ubuntu drops /usr/bin/pebble into the base layer without a dpkg package
# owning it, so apt can neither patch nor purge the CVEs vendored into it
# (CVE-2026-39821). This image only runs caddy, so drop it.
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get upgrade -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
    ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -f /usr/bin/pebble && rm -rf /var/lib/pebble

COPY --from=caddy_builder /usr/bin/caddy /usr/bin/caddy

# Same layout as the official image, so the Compose services can mount their
# Caddyfile and the caddy_config / caddy_data volumes unchanged.
ENV XDG_CONFIG_HOME=/config \
    XDG_DATA_HOME=/data
RUN mkdir -p /config/caddy /data/caddy /etc/caddy /baserow/media && \
    caddy version

EXPOSE 80 443 443/udp

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
