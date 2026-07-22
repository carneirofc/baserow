# deploy

## Purpose

Deployment artifacts for running Baserow: the single-container "all-in-one" image and the Kubernetes/OpenShift Helm chart.

## Ownership

Owns everything under `deploy/`:

- `all-in-one/` — self-contained image bundling backend, frontend, workers, and supervisor (`baserow.sh`, `Dockerfile`, `docker-compose.yml`, `supervisor/`).
- `helm/baserow/` — Helm chart (`Chart.yaml`, `values.yaml`, `values-openshift.yaml`, `templates/`, subcharts).
- `plugins/` — plugin packaging helpers.

The root `docker-compose.yaml` / `docker-compose.yml` and `Caddyfile*` are the local/dev entrypoints and stay owned by the root.

## Local Contracts

- This is a FOSS fork: image references, registries, chart names, and branding must point at this fork's infrastructure, **not** Baserow B.V. Do not reintroduce upstream pointers.
- Keep `values-openshift.yaml` compatible with OpenShift's restricted SCC (no fixed UIDs/root, arbitrary-UID-safe) when editing the chart.
- Bump `Chart.yaml` `version`/`appVersion` on chart changes; keep `Chart.lock` and subcharts consistent.

## Work Guidance

- Validate chart edits with `helm lint deploy/helm/baserow` and `helm template` before shipping.
- Keep the all-in-one image and the Compose/Helm envs in sync with backend/frontend env-var contracts.

## Verification

No repo-wired check yet; use `helm lint`/`helm template` and a local `docker compose` bring-up.

## Child DOX Index

None.
