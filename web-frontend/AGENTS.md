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
- Every backend permission manager whose `get_permissions_object` returns data needs a frontend `permissionManager` of the same type (`modules/core/permissionManagerTypes.js`). `plugins/permissions.js` skips unknown types, so a missing one silently lets a later manager allow what the backend denies.
- User-facing strings go through **i18n** (`locales/`, `i18n.config.ts`), not inline literals.
- The `prod` image ships only `.output` (`Dockerfile`), never `node_modules`. That is what keeps Go-compiled npm binaries — esbuild, pulled in by `nitropack` and `vite` — out of the runtime image; SCA scanners read the Go stdlib embedded in such binaries and report it against the image. The `ci` and `dev` targets do carry `node_modules` and therefore do contain them.
- Runtime branding (`docs/installation/branding.md`) must keep working without a rebuild. `modules/core/server/branding/` (Nitro handlers registered in `modules/core/module.js`) serves `/_branding/theme.css`, `/_branding/config.json` and `/_branding/assets/{img,icons,files}/…` from `BASEROW_BRANDING_DIR`, falling back to defaults bundled as Nitro server assets (`branding-img`, `branding-icons`); `plugins/branding.js` applies the title, translation overrides and theme stylesheet during SSR.
- Anything branding may override (logo and favicon references, the `baserow-icon` masks in `icons.scss`) must load through the `/_branding/assets/` route, never a bundled `?url` import or a `public`/`static` path: Nitro serves public assets before any handler, so a public path cannot be overridden.
- Color tokens in `assets/scss/colors.scss` are CSS custom properties (`token()` → `var(--name, default)`). Never apply Sass color functions (`rgba`, `darken`, `mix`, `red()`…) to `$palette-*`/`$color-*` — the build fails on `var()` — use `alpha($color, $opacity)` or CSS `color-mix()`, and never interpolate tokens into data URIs. `$white`/`$black` stay literal.
- Keep this file free of nested lists: the root `.editorconfig` (4-space Markdown indent) is absent from the CI image, so prettier formats nested list indentation differently locally and in CI.
- `branding.json` values are validated server-side (token names, CSS color values, font, locale keys) so they cannot inject CSS; keep that validation when adding settings.
- The `node-base` stage deletes Ubuntu's unowned `/usr/bin/pebble` (CVE-2026-39821) for the same reason npm/yarn are dropped from `local`: unreachable code that scanners still report. Every stage here descends from `node-base`, so the single removal covers them all — see `deploy/AGENTS.md` for the repo-wide rule.
- `components/backups/{BackupsTab,BackupSchedulesTab,RemoteBackupsTab}.vue` accept an optional `service` prop (a `(client) => {...}` factory, defaulting to `services/backup.js`) so the same tabs render both the member-facing `BackupsModal` (workspace context menu) and the staff-only `pages/admin/backups.vue` (`components/admin/backups/BackupsAdminPanel.vue`, `services/admin/backups.js` hitting `/admin/backups/...`). Extend this prop, don't fork the components, when another surface needs the same tabs against a different endpoint.

- Protected editing (`table.require_edit_confirmation`, `modules/database/utils/editConfirmation.js`): on such tables a single cell or row modal edit is staged in the `pendingRowChanges` store and saved in one batch update by `PendingChangesBar`, and every other row mutation (create, paste, clear, delete, move, undo/redo) first awaits `confirmDataChange(store, table, …)`, rendered by the `ConfirmDataChangeModal` host mounted in `components/table/Table.vue`. A new row mutation entry point must honor the same helpers.

## Work Guidance

- Run frontend tasks via `just frontend <recipe>` (aliases `just f …`): `check`/`lint`, `fix`/`format`, `test`, `run-dev-server`, `storybook`, `build-nuxt`.
- Lint/format is **eslint** + **stylelint** (`eslint.config.mjs`, `stylelint.config.mjs`).
- Tests are **Vitest** (Vue Test Utils / TestApp); update snapshots with `just frontend update-snapshots` only when intended.
- Prefer the `write-frontend-unit-test` skill; UI element work is covered by `add-update-builder-element-type` and `create-in-app-notification`. Locate files to change first with `find-change-candidates`.
- Add a changelog entry for user-facing changes (`just changelog add`).

## Verification

- Tests: `just frontend test` (Vitest); CI variant `just frontend ci-test`.
- Lint: `just frontend lint`. Both must pass before commit (also enforced by pre-commit).
- CI job `web-frontend-prod-image` (`.github/workflows/ci.yml`) builds the `prod` target, asserts no esbuild artefact is present anywhere in the exported image filesystem, and boots it against `/_health/`.

## Child DOX Index

No child AGENTS.md yet. Feature modules are documented via project skills; add a child only if a module gains its own durable, skill-independent contract.
