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
- `DownloadLink` (`modules/core/components/DownloadLink.vue`) preflights every download with a `HEAD` and only then hands the browser the link, because a plain anchor cannot report a failure and would render the server's error page where the file should be. It maps the status to a message: 410 is an expired file, 500 and 503 are the server's own file storage, and those two must never read as "file not found". Bind it to a job's `download_url`, never to `url` — the latter points straight at the storage and is unreachable in most container deployments. User file attachments still use `url`.
- User-facing strings go through **i18n** (`locales/`, `i18n.config.ts`), not inline literals.
- `config/locales.js` is the single source of truth for shipped languages (currently `en` and `pt-BR`); every module registers it (`modules/*/module.js`) and so does `config/nuxt.config.base.ts`. A registered code needs its JSON file in **every** `locales/` dir — each module's and the root `web-frontend/locales/` — or `yarn run build` dies with `ENOENT` in `computeLocaleHashes`; an empty `{}` is enough, since `modules/core/plugins/i18n.js` falls back to English. Keep the code list equal to `LANGUAGES` in `backend/src/baserow/config/settings/base.py` (the account language endpoint validates against it) and keep `modules/core/moment.js` importing the matching moment locales. Components read the list via `useI18n()`; never hardcode one.
- The `prod` image ships only `.output` (`Dockerfile`), never `node_modules`. That is what keeps Go-compiled npm binaries — esbuild, pulled in by `nitropack` and `vite` — out of the runtime image; SCA scanners read the Go stdlib embedded in such binaries and report it against the image. The `ci` and `dev` targets do carry `node_modules` and therefore do contain them.
- Runtime branding (`docs/installation/branding.md`) must keep working without a rebuild. `modules/core/server/branding/` (Nitro handlers registered in `modules/core/module.js`) serves `/_branding/theme.css`, `/_branding/config.json` and `/_branding/assets/{img,icons,files}/…` from `BASEROW_BRANDING_DIR`, falling back to defaults bundled as Nitro server assets (`branding-img`, `branding-icons`); `plugins/branding.js` applies the title, translation overrides and theme stylesheet during SSR.
- Anything branding may override (logo and favicon references, the `baserow-icon` masks in `icons.scss`) must load through the `/_branding/assets/` route, never a bundled `?url` import or a `public`/`static` path: Nitro serves public assets before any handler, so a public path cannot be overridden.
- Color tokens in `assets/scss/colors.scss` are CSS custom properties (`token()` → `var(--name, default)`). Never apply Sass color functions (`rgba`, `darken`, `mix`, `red()`…) to `$palette-*`/`$color-*` — the build fails on `var()` — use `alpha($color, $opacity)` or CSS `color-mix()`, and never interpolate tokens into data URIs. `$white`/`$black` stay literal.
- No hard-coded hex colors in SCSS outside `colors.scss`: use the nearest `$palette-*`/`$color-*` token so branding reaches it. The exceptions are the hue/saturation gradients in `color_picker.scss` and the `var(--page-background-color, #fff)` builder-theme fallbacks.
- Sass: only the `import` deprecation is silenced (`config/nuxt.config.base.ts`); don't add others back, fix them instead (`sass:string`/`sass:map` module functions, `@if` instead of `if()`). The `@import` → `@use` migration is pending because `@use` needs explicit wiring for the ~220 `@extend %placeholder` rules and reorders the emitted CSS.
- Icon classes (`iconoir-*`) must exist in the installed iconoir version; a missing class renders blank with no error. After an iconoir upgrade, diff the class list in `node_modules/iconoir/css/iconoir.css` against the classes the code uses.
- Plural messages written with `{n}` must be called with the count as the plural argument (`$t(key, days)`); passing `{ count: days }` leaves `{n}` empty and never selects a plural form.
- Retention and expiry values the UI states (trash hours, export file expiry, snapshot expiry, audit log and row history retention) are Django settings mirrored into Nuxt runtime config: default in `modules/core/module.js`, remap in `env-remap.mjs`, and the env var passed to the **web-frontend service too** (`docker-compose.yml`; the Helm chart already shares one configmap). Miss the last step and the UI quietly shows its own default instead of what the backend enforces. Treat a non-positive value as "cleanup switched off" and show nothing. Staff-only limits belong in `/admin/limits/` (`services/admin/limits.js`), not in runtime config, which is public.
- Build metadata (`appVersion`, `gitCommit`, `buildDate` in `modules/core/module.js`, provided as `$buildInfo` by `plugins/version.js`) identifies the bundle a viewer has open. It is baked in from the `BASEROW_BUILD_*` docker build args, and `env-remap.mjs` maps those three only when non-empty, because an orchestrator that forwards an unset variable would otherwise blank out the version the image was built with. Empty means a development build: `utils/buildInfo.js` returns an empty label for it and every surface (`layouts/login.vue`, `SidebarUserContext`, `components/version/BuildInfo.vue`) must render nothing rather than an empty row. The backend reports its own build through `/admin/build/`; a commit mismatch between the two is shown as a warning, and a failed request is rendered as an explicit "could not be read" state (a backend older than the web-frontend has no such endpoint), so don't collapse the two builds into one value and don't swallow the request error.
- Job elapsed time comes from `utils/job.js` + the `mixins/jobElapsed.js` ticker, rendered by `components/job/JobDuration.vue`. It ticks on its own 1s interval, not on job updates, because the poller backs off up to `baserowFrontendJobsPollingTimeoutMs`. Add it next to a `ProgressBar`, never to a UI whose bar blends non-job progress (`ImportFileModal` mixes upload and job percentages, so a job-only duration would misreport there).
- Keep this file free of nested lists: the root `.editorconfig` (4-space Markdown indent) is absent from the CI image, so prettier formats nested list indentation differently locally and in CI.
- `branding.json` values are validated server-side (token names, CSS color values, font, locale keys, `http(s)`/root-relative URLs) so they cannot inject CSS or a `javascript:` href; keep that validation when adding settings.
- Attribution and help links come from `$branding` (`siteUrl`, `docsUrl`, `siteTitle`, `showAttribution`), provided by `plugins/branding.js` and defaulted in `modules/core/brandingDefaults.js`. Never hardcode a project URL in a component; anything gated on `showAttribution` must render nothing when it is false.
- The `node-base` stage deletes Ubuntu's unowned `/usr/bin/pebble` (CVE-2026-39821) for the same reason npm/yarn are dropped from `local`: unreachable code that scanners still report. Every stage here descends from `node-base`, so the single removal covers them all — see `deploy/AGENTS.md` for the repo-wide rule.
- `components/backups/{BackupsTab,BackupSchedulesTab,RemoteBackupsTab}.vue` accept an optional `service` prop (a `(client) => {...}` factory, defaulting to `services/backup.js`) so the same tabs render both the member-facing `BackupsModal` (workspace context menu) and the staff-only `pages/admin/backups.vue` (`components/admin/backups/BackupsAdminPanel.vue`, `services/admin/backups.js` hitting `/admin/backups/...`). Extend this prop, don't fork the components, when another surface needs the same tabs against a different endpoint.

- API clients (`components/apiClients/`, `services/apiClients.js`, `apiClients/scopes.js`): per-workspace, per-user integration credentials opened from `WorkspaceContext`, deliberately ungated because `/api/api-clients/...` is `IsAuthenticated` and lists only the caller's own clients. `scopes.js` mirrors `ALL_SCOPES` in `baserow.core.api_clients.scopes` and must stay in sync with it. A created key's full secret exists only in the create response: hand it straight to `ApiClientKeyRevealModal` and never store it on the key kept in the list. Revoking a key returns the updated record rather than deleting it, so update the row in place and keep it visible.

- CrudTable filtering (`components/crudTable/CrudTable.vue`): pass `:filters` and fill the `#header-filters` slot, as `components/admin/auditLog/` does. Filters go straight into the query string and the backend applies an exact lookup per filter, so a blank one must be absent from the object entirely — build it with `omitEmptyFilters` (`services/admin/auditLog.js`). Anything that reproduces a CrudTable request outside the table (exporting what is on screen) must reuse `serializeSorts` from `crudTable/baseService.js` so it cannot drift from what `fetch` sends.

- Protected editing (`table.require_edit_confirmation`, `modules/database/utils/editConfirmation.js`): on such tables a single cell or row modal edit is staged in the `pendingRowChanges` store and saved in one batch update by `PendingChangesBar`, and every other row mutation (create, paste, clear, delete, move, undo/redo) first awaits `confirmDataChange(store, table, …)`, rendered by the `ConfirmDataChangeModal` host mounted in `components/table/Table.vue`. A new row mutation entry point must honor the same helpers. `ImportFileModal` is the one exception: an import changes a whole set of rows, so it always refreshes the preview and asks for acceptance through its own `ConfirmImportModal` (the `confirmDataChange` host only exists on the table page, and the generic confirmation cannot render the change counts), it refuses to submit while the table has staged changes, and it gates the `replace` mode and `delete_unmatched` on `database.table.replace_rows`.

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
