# Baserow Helm chart (OpenShift-hardened)

Deploys this Baserow fork on Kubernetes/OpenShift as separate, hardened pods —
`backend`, `web-frontend`, `celery` worker and `celery-beat` — plus optional,
toggleable PostgreSQL and Redis subcharts.

The chart is built to run **unmodified under OpenShift's default `restricted-v2`
SCC**: non-root, arbitrary UID, read-only root filesystem, dropped capabilities,
unprivileged ports (8000/3000). **No cluster security change is required** and the
chart never sets `runAsUser`/`fsGroup` (the SCC assigns them).

> The all-in-one image is intentionally **not** used here: it starts as root,
> drops to a fixed UID via `su-exec`, chowns its data dir and binds `:80` — none
> of which is allowed under `restricted-v2`. The standalone `backend` and
> `web-frontend` images already satisfy the policy.

## Routing

Backend and web-frontend share one origin (the Route host). OpenShift Routes
demux by path — `/api`, `/ws`, `/mcp`, `/assistant`, `/static` go to the backend,
everything else to the web-frontend — so there is no reverse-proxy pod and no CORS
configuration. `/media` is served from object storage.

## Quick start

```sh
# 1. Fetch the PostgreSQL/Redis subcharts
helm dependency build deploy/helm/baserow

# 2. Render/inspect (both DB modes)
helm template baserow deploy/helm/baserow -f deploy/helm/baserow/values-openshift.yaml
helm template baserow deploy/helm/baserow --set postgresql.enabled=true

# 3. Install
helm install baserow deploy/helm/baserow \
  -n baserow --create-namespace \
  -f deploy/helm/baserow/values-openshift.yaml
```

## Database provisioning (optional & configurable)

| Mode | Values |
| --- | --- |
| Bundled (default) | `postgresql.enabled: true` — Bitnami subchart, password auto-managed in Secret `<release>-postgresql`. |
| External (recommended for prod) | `postgresql.enabled: false` + `externalDatabase.*` (or `externalDatabase.existingSecret`). |

Redis mirrors this with `redis.enabled` / `externalRedis.*`. Subcharts set
`global.compatibility.openshift.adaptSecurityContext=auto` so they too obey
`restricted-v2`; for production a managed database is still the recommended path.

## Media storage

- **Object storage (default, recommended):** `objectStorage.enabled: true` with
  `bucketName`, `endpointURL`, `region` and S3 credentials (inline or
  `existingSecret` with keys `s3-access-key-id` / `s3-secret-access-key`). Pods
  stay stateless and scale past one replica.
- **PVC fallback:** `objectStorage.enabled: false` creates an RWO PVC mounted on
  backend + celery and serves uploads through the backend. Keep `replicaCount.backend: 1`
  unless your storage class supports ReadWriteMany.

## Personalization

- **Favicon (runtime):** set `branding.faviconBase64` to the base64 of your
  `.ico`; it is mounted over the served favicon. No rebuild needed.
- **App name, logo, color palette (build-time):** these are compiled into the
  web-frontend image and cannot be changed at deploy time. Rebuild the fork image
  (`Logo.vue`, `colors.scss` `$palette-*`, app title strings) and point
  `image.webFrontend.tag` / `image.backend.tag` at it.

## Secrets

Unless `secrets.existingSecret` is set, the chart creates `<release>-baserow`
with a generated `secret-key` and `jwt-signing-key` (preserved across upgrades).
For external DB/Redis/S3 without their own secrets, it also holds
`database-password`, `redis-password`, `s3-access-key-id`, `s3-secret-access-key`.

## Notes / limitations

- Custom builder domains (the all-in-one's on-demand-TLS feature) are not wired
  through path Routes; use the primary Route host.
- `migrateOnStartup: true` runs migrations from the backend pod on boot. For
  strict zero-downtime upgrades, split this into a pre-upgrade Job later.
- Validate on your cluster: `helm lint deploy/helm/baserow`,
  `helm install --dry-run`, then `oc get pods -l app.kubernetes.io/instance=<release>`.
