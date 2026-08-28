# web-frontend

## Purpose

Nuxt/Vue web application for Baserow: the browser UI for databases, the Application Builder, Automation, Dashboards, and admin.

## Ownership

Owns everything under `web-frontend/`: `modules/` (feature code), `test/`, `stories/`, `locales/`/`i18n/`, `public/`, Nuxt/Vite/Vitest config, `package.json`, and `Dockerfile`.

- `modules/core/` — shared app shell, registries, components, and services.
- `modules/database/`, `modules/builder/`, `modules/automation/`, `modules/dashboard/`, `modules/integrations/` — feature modules mirroring the backend `contrib` domains.

## Local Contracts

- Package manager is **yarn** (`yarn.lock`); Node version pinned by `.nvmrc`.
- Frontend mirrors the backend **registry** pattern — feature types register into module registries; extend via registration, not hardcoding.
- Keep the frontend contract in sync with the backend API it consumes (serializers, error codes, URLs).
- User-facing strings go through **i18n** (`locales/`, `i18n.config.ts`), not inline literals.
- The `prod` image ships only `.output`, and `Dockerfile` deletes the esbuild binary Nitro traces into it: esbuild is Go-compiled, never runs in production, and its embedded Go stdlib shows up in SCA scans of the published image. Keep the strip and its assertion when touching the build stages.

## Work Guidance

- Run frontend tasks via `just frontend <recipe>` (aliases `just f …`): `check`/`lint`, `fix`/`format`, `test`, `run-dev-server`, `storybook`, `build-nuxt`.
- Lint/format is **eslint** + **stylelint** (`eslint.config.mjs`, `stylelint.config.mjs`).
- Tests are **Vitest** (Vue Test Utils / TestApp); update snapshots with `just frontend update-snapshots` only when intended.
- Prefer the `write-frontend-unit-test` skill; UI element work is covered by `add-update-builder-element-type` and `create-in-app-notification`.
- Add a changelog entry for user-facing changes (`just changelog add`).

## Verification

- Tests: `just frontend test` (Vitest); CI variant `just frontend ci-test`.
- Lint: `just frontend lint`. Both must pass before commit (also enforced by pre-commit).
- CI job `web-frontend-prod-image` (`.github/workflows/ci.yml`) builds the `prod` target, asserts no esbuild artefact survives in the image, and boots it against `/_health/`.

## Child DOX Index

No child AGENTS.md yet. Feature modules are documented via project skills; add a child only if a module gains its own durable, skill-independent contract.
