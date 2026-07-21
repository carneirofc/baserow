# CI/CD overview

This fork runs entirely on **GitHub Actions**. There are two workflows that matter for
building and shipping code, both defined in `.github/workflows/`:

| Workflow | File | Trigger | Purpose |
| --- | --- | --- | --- |
| CI Pipeline | `ci.yml` | PRs, pushes to `develop`/`master`, manual dispatch | Lint and test every change |
| Build & Publish All-in-One Image | `build-publish-image.yml` | `v*` tags | Build and publish the release container |

## CI Pipeline (`ci.yml`)

Runs on every pull request, on pushes to `develop`/`master`, and on manual dispatch.
In-progress runs for the same branch/PR are cancelled automatically.

A `detect-changes` step uses path filters so unaffected suites are skipped (a docs-only
PR does not run the backend tests, etc.). The jobs are:

- **Lint** — `backend-lint` (Ruff), `frontend-lint` (ESLint/Stylelint/Prettier),
  `dockerfile-lint` (hadolint).
- **Tests** — `backend-check-startup`, `test-backend` (parallel groups),
  `test-frontend` (sharded Vitest), `test-zapier`, `check-mjml-compiled`,
  `test-e2e` (sharded), plus `collect-coverage` and `collect-e2e-reports`.
- **build-backend** / **build-frontend** — build the CI Docker images the test jobs run
  inside, pushed to GHCR with a short-lived `ci-<sha>` tag.
- **ci-status** — aggregates the above into a single required check for branch
  protection. Jobs listed in the `OPTIONAL_CHECKS` repository variable are allowed to
  fail without blocking the merge.

`ci.yml` does not publish release images. Upstream Baserow's image build-and-publish jobs
(`build-final-*`, `publish-develop-latest-*`, `trigger-saas-build`) pushed to Baserow
B.V.'s own registry and SaaS pipeline; they have been removed from this fork. Release
publishing is handled entirely by the workflow below.

## Build & Publish All-in-One Image (`build-publish-image.yml`)

This is how the fork ships a container. On any `v*` tag it builds, in one `linux/amd64`
job, using only the built-in `GITHUB_TOKEN` (no external secrets):

1. the backend image from `backend/Dockerfile` (`prod` target),
2. the web-frontend image from `web-frontend/Dockerfile` (`prod` target),
3. the all-in-one image from `deploy/all-in-one/Dockerfile`, fed the two images above via
   its `BACKEND_IMAGE` / `WEBFRONTEND_IMAGE` build args.

Because backend and web-frontend are built from this repository's source, the published
image contains the fork's changes.

The result is pushed to this repo's GitHub Container Registry as
`ghcr.io/<owner>/<repo>/baserow`, tagged by `docker/metadata-action` with the full
version, `major.minor`, `major`, and `latest`. Steps 1 and 2 also push short-lived
`backend:build-<sha>` / `web-frontend:build-<sha>` intermediates that the all-in-one
build consumes.

## Cutting a release

```bash
git tag v1.2.3
git push origin v1.2.3
```

Pushing the tag triggers `build-publish-image.yml`, which publishes
`ghcr.io/carneirofc/baserow/baserow:1.2.3` and `:latest`. GHCR packages are private by
default — make the package public (or `docker login ghcr.io`) to allow anonymous pulls.

## Reproducing CI locally

The GitHub jobs delegate to the same `just` recipes you run locally, so there is no
CI-only configuration to reproduce:

```bash
just lint          # backend + frontend linters
just b test -n=auto
just f test
```

See [building-and-running-production-images.md](./building-and-running-production-images.md)
for building the images by hand.
