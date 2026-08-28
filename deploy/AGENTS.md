# deploy

## Purpose

Deployment artifacts for running Baserow: the single-container "all-in-one" image and the Kubernetes/OpenShift Helm chart.

## Ownership

Owns everything under `deploy/`:

- `all-in-one/` — self-contained image bundling backend, frontend, workers, and supervisor (`baserow.sh`, `Dockerfile`, `docker-compose.yml`, `supervisor/`).
- `helm/baserow/` — Helm chart (`Chart.yaml`, `values.yaml`, `values-openshift.yaml`, `templates/`, subcharts).
- `caddy/` — standalone Caddy reverse-proxy image for the split-services Compose stacks; published as `ghcr.io/<owner>/<repo>/caddy` by `.github/workflows/build-publish-image.yml`.
- `plugins/` — plugin packaging helpers.

The root `docker-compose.yaml` / `docker-compose.yml` and `Caddyfile*` are the local/dev entrypoints and stay owned by the root.

## Local Contracts

- This is a FOSS fork: image references, registries, chart names, and branding must point at this fork's infrastructure, **not** Baserow B.V. Do not reintroduce upstream pointers.
- Keep `values-openshift.yaml` compatible with OpenShift's restricted SCC (no fixed UIDs/root, arbitrary-UID-safe) when editing the chart.
- Bump `Chart.yaml` `version`/`appVersion` on chart changes; keep `Chart.lock` and subcharts consistent.
- All three images (`backend/Dockerfile`, `web-frontend/Dockerfile`, `all-in-one/Dockerfile`) build on `ubuntu:26.04` and take PostgreSQL 18 and Redis from the Ubuntu archive — no third-party apt repositories. The all-in-one copies the backend venv, so its base must keep providing the same `python3` as the backend image.
- Node is installed from the SHA256-pinned nodejs.org tarball in both `web-frontend/Dockerfile` (`node-base`) and `all-in-one/Dockerfile`; keep `NODE_VERSION`, the per-arch SHA256s and `YARN_VERSION` identical in both. The all-in-one installs its own copy because the web-frontend `prod` target deletes npm/yarn, which `plugins/*.sh` needs.
- Caddy is built from source in `all-in-one/Dockerfile` and `caddy/Dockerfile` (`golang:${GO_VERSION}` stage, `go install caddy@v${CADDY_VERSION}`) rather than copied out of the official `caddy` image, which lags behind Go security releases. Keep `GO_VERSION` and `CADDY_VERSION` identical in both; bump `GO_VERSION` when a Go patch release fixes a reported CVE and `CADDY_VERSION` for Caddy releases.
- `.github/workflows/build-publish-image.yml` builds every image with `pull: true`, so a `v*` tag cut re-resolves `ubuntu:26.04` and `golang:${GO_VERSION}` instead of serving a stale GHA cache hit. Cutting a release is therefore the way to republish images against upstream security rebuilds when no source changed.
- Bumping the embedded PostgreSQL major version is a breaking change for all-in-one users: update `docs/runbooks/upgrade-embedded-postgres.md` and the version guard in `all-in-one/supervisor/docker-postgres-setup.sh` together.

## Work Guidance

- Validate chart edits with `helm lint deploy/helm/baserow` and `helm template` before shipping.
- Keep the all-in-one image and the Compose/Helm envs in sync with backend/frontend env-var contracts.

## Verification

- `.github/workflows/publish-helm-chart.yml` lints, renders, and packages the chart on PRs touching `deploy/helm/**`, and on `v*` tags pushes it to `oci://ghcr.io/<owner>/<repo>/charts/baserow` (chart version from `Chart.yaml`).
- Locally: `helm lint`/`helm template` and a `docker compose` bring-up.

## Child DOX Index

None.
