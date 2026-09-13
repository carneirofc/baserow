# deploy

## Purpose

Deployment artifacts for running Baserow: the single-container "all-in-one" image and the Kubernetes/OpenShift Helm chart.

## Ownership

Owns everything under `deploy/`:

- `all-in-one/` — self-contained image bundling backend, frontend, workers, and supervisor (`baserow.sh`, `Dockerfile`, `docker-compose.yml`, `supervisor/`).
- `helm/baserow/` — Helm chart (`Chart.yaml`, `values.yaml`, `values.schema.json`, `values-openshift.yaml`, `values-eks.yaml`, `templates/`, subcharts).
- `caddy/` — standalone Caddy reverse-proxy image for the split-services Compose stacks; published as `ghcr.io/<owner>/<repo>/caddy` by `.github/workflows/build-publish-image.yml`.
- `plugins/` — plugin packaging helpers.

The root `docker-compose.yaml` / `docker-compose.yml` and `Caddyfile*` are the local/dev entrypoints and stay owned by the root.

## Local Contracts

- This is a FOSS fork: image references, registries, chart names, and branding must point at this fork's infrastructure, **not** Baserow B.V. Do not reintroduce upstream pointers.
- Keep `values-openshift.yaml` compatible with OpenShift's restricted SCC (no fixed UIDs/root, arbitrary-UID-safe) when editing the chart.
- The chart targets plain Kubernetes, OpenShift and EKS. Every shipped values preset (`values.yaml`, `values-openshift.yaml`, `values-eks.yaml`) must stay lint-clean and renderable on its own — CI lints and `kubeconform`-validates all three, so a preset that needs a `--set` to render is broken. Default values stay platform-neutral: `openshift.route.enabled` defaults to `false` and CI fails if stock values render a `Route`.
- `values.schema.json` is enforced by Helm on lint/template/install. Adding a value means adding it there too; `postgresql` and `redis` stay `additionalProperties: true` so subchart values pass through.
- In `objectStorage.auth: irsa`/`podIdentity` the chart must render **no** `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` and write no `s3-*` Secret keys — omitted entirely, never emitted empty. The backend's `set_setting_from_env_if_present` (`backend/src/baserow/config/settings/utils.py`) reads `os.getenv(var, None)`, so a present-but-empty variable sets the Django setting to `""` and boto3 uses that instead of falling through to the pod's web identity token. `_helpers.tpl`'s `baserow.objectStorage.useStaticKeys` is the single gate for this; `publish-helm-chart.yml` asserts the IRSA render stays credential-free.
- `objectStorage.defaultACL` defaults to `""` (send no ACL). The backend defaults `AWS_DEFAULT_ACL` to `public-read`, which every bucket with ACLs disabled rejects with `AccessControlListNotSupported`; do not reintroduce a non-empty default.
- `ingress.mode: albGroup` renders two Ingress objects joined by `alb.ingress.kubernetes.io/group.name`. It exists because the AWS Load Balancer Controller resolves `healthcheck-path` per Ingress, so a single Ingress cannot give the backend and web-frontend target groups different health endpoints. The controller merges Service annotations over Ingress annotations, which is what `service.<component>.annotations` is for.
- Deployments carry `checksum/config` and `checksum/secret` pod annotations (`baserow.podAnnotations`). New workloads must include them, or config-only `helm upgrade`s silently leave pods on stale values. `checksum/secret` hashes the credential **values**, never the rendered `secret.yaml`: that template falls back to `randAlphaNum` whenever `lookup` finds no live Secret, so hashing its output changes on every render and would roll every pod on each Argo CD sync. CI asserts these annotations are identical across two renders.
- Bump `Chart.yaml` `version` on chart changes (and `appVersion` on release cuts); keep `Chart.lock` and subcharts consistent. The `version-bump` job in `publish-helm-chart.yml` fails any PR touching `deploy/helm/**` without a version bump.
- Runtime web-frontend branding (`docs/installation/branding.md`) reaches every deployment as a directory at `BASEROW_BRANDING_DIR`:
  - **Helm:** `templates/configmap-branding.yaml` renders `branding.*` values, with `files` keys flattened `/`→`__` and mapped back through `items` in `webfrontend-deployment.yaml`, mounted read-only at `/baserow/branding`. `branding.existingClaim` mounts a PVC instead. `faviconBase64` also keeps its subPath mount over `.output/public/favicon.ico`. The branding ConfigMap is covered by `checksum/branding` in `baserow.podAnnotations`.
  - **All-in-one:** `supervisor/default_baserow_env.sh` defaults the directory to `$DATA_DIR/branding`.
  - **Compose:** the root `docker-compose.yaml` forwards `BASEROW_BRANDING_*` and documents the optional mount.
  - Example directory: `branding-example/`.
- Backend settings the chart does not model explicitly go through `values.yaml`'s `extraEnv` map, rendered into the shared app ConfigMap by `templates/configmap-env.yaml`. That is how SSO and RBAC are configured (`BASEROW_OIDC_PROVIDERS`, `BASEROW_OIDC_ONLY`, `BASEROW_ROLES`); the root `docker-compose.yaml` forwards the same three from the environment. The ConfigMap is not encrypted, so secrets belong elsewhere.
- All three images (`backend/Dockerfile`, `web-frontend/Dockerfile`, `all-in-one/Dockerfile`) build on `ubuntu:26.04` and take PostgreSQL 18 and Redis from the Ubuntu archive — no third-party apt repositories. The all-in-one copies the backend venv, so its base must keep providing the same `python3` as the backend image.
- Every stage built on `ubuntu:26.04` deletes `/usr/bin/pebble` and `/var/lib/pebble` in its first `RUN`. Canonical drops that binary into the base layer without a dpkg package owning it, so `apt-get upgrade`/`purge` cannot touch the CVEs vendored into it (CVE-2026-39821), and no image here executes it. A new `ubuntu:26.04` stage must repeat the removal — each `FROM` restarts from the pristine base layer. The `dockerfile-lint` job in `ci.yml` statically asserts every `ubuntu:26.04` stage carries the removal; `caddy-image-build` and `web-frontend-prod-image` assert it is absent from the images they build, and `build-publish-image.yml` does the same for the backend, web-frontend and all-in-one images it publishes.
- Node is installed from the SHA256-pinned nodejs.org tarball in both `web-frontend/Dockerfile` (`node-base`) and `all-in-one/Dockerfile`; keep `NODE_VERSION`, the per-arch SHA256s and `YARN_VERSION` identical in both. The all-in-one installs its own copy because the web-frontend `prod` target deletes npm/yarn, which `plugins/*.sh` needs.
- Caddy is built from source in `all-in-one/Dockerfile` and `caddy/Dockerfile` (`golang:${GO_VERSION}` stage, Caddy `v${CADDY_VERSION}` built from a generated module) rather than copied out of the official `caddy` image, which lags behind Go security releases. Keep `GO_VERSION` and `CADDY_VERSION` identical in both; bump `GO_VERSION` when a Go patch release fixes a reported CVE and `CADDY_VERSION` for Caddy releases. Caddy is built in module mode (a generated `main.go` + `go get`, as xcaddy does) so `CADDY_MODULE_UPGRADES` can raise Go modules compiled into the binary (e.g. `golang.org/x/*`, grpc) past what the Caddy release pins; keep that list identical in both Dockerfiles, raise an entry when the image CVE scan flags a module in `/usr/bin/caddy`, and drop it once `CADDY_VERSION` requires that version or newer.
- Images are CVE-gated with Trivy (HIGH/CRITICAL with a fix, exceptions in root `.trivyignore.yaml`): `ci.yml` scans the caddy and web-frontend prod images it builds, and `build-publish-image.yml` scans all four published images after push, failing the release run. Locally: `just audit images <refs>`.
- `.github/workflows/build-publish-image.yml` builds every image with `pull: true`, so a `v*` tag cut re-resolves `ubuntu:26.04` and `golang:${GO_VERSION}` instead of serving a stale GHA cache hit. Cutting a release is therefore the way to republish images against upstream security rebuilds when no source changed.
- Every image reference points at this fork's registry (`ghcr.io/carneirofc/baserow/{backend,web-frontend,baserow,caddy}`), including the `BACKEND_IMAGE`/`WEBFRONTEND_IMAGE` defaults in `all-in-one/Dockerfile`. Never reference Docker Hub `baserow/*` — those are Baserow B.V.'s images, and a stack pointed at them silently runs and gets scanned as upstream code.
- The images target PostgreSQL 18, so every database beside them is pinned to `pgvector/pgvector:pg18` — the root `docker-compose.yaml`/`docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.e2e-infra.yml`, the `ci.yml` service blocks, and the `justfile` ramdisk test DB. Bump them together; a split leaves `pg_dump` talking to an older server than its own major.
- Bumping the embedded PostgreSQL major version is a breaking change for all-in-one users: update `docs/runbooks/upgrade-embedded-postgres.md` and the version guard in `all-in-one/supervisor/docker-postgres-setup.sh` together.

## Work Guidance

- Validate chart edits with `helm lint --strict deploy/helm/baserow` and `helm template` against all three values presets before shipping, then pipe the render through `kubeconform -strict -ignore-missing-schemas` (`-ignore-missing-schemas` covers the OpenShift `Route` CRD). `kubectl apply --dry-run=client` is not a substitute — it downloads the OpenAPI schema from a live cluster.
- User-facing chart docs live in `docs/installation/install-with-helm.md` (values reference, day-two ops) and `docs/installation/install-on-eks.md` (internal ALB + CloudFront VPC origin, IRSA). `deploy/helm/README.md` is the short orientation page that links to both; keep the three consistent.
- Keep the all-in-one image and the Compose/Helm envs in sync with backend/frontend env-var contracts.

## Verification

- `.github/workflows/publish-helm-chart.yml` runs on PRs touching `deploy/helm/**` and on `v*` tags. It gates the chart version bump, lints and `kubeconform`-validates all three values presets plus five option combinations, asserts the IRSA render carries no static credentials and that default values render no OpenShift `Route`, then packages the chart. On `v*` tags it pushes to `oci://ghcr.io/<owner>/<repo>/charts/baserow` (chart version from `Chart.yaml`).
- Locally: `helm lint --strict`/`helm template` + `kubeconform`, and a `docker compose` bring-up.

## Child DOX Index

None.
