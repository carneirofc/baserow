# backend

## Purpose

Django backend for Baserow: REST API, real-time WebSocket layer, Celery workers, and the domain logic behind databases, the Application Builder, Automation, Dashboards, and integrations.

## Ownership

Owns everything under `backend/`: `src/baserow/` (source), `tests/` (pytest suite), `Dockerfile`, `pyproject.toml`, `pytest.ini`, `mypy.ini`, `justfile`, and packaging.

- `src/baserow/core/` — cross-cutting platform: registries, permissions, jobs, import/export, backups and backup schedules, cron scheduling helpers (`core/scheduling/cron.py`, shared by every cron-driven schedule), contents, API clients, auth, formulas, notifications, MCP.
- `src/baserow/contrib/` — feature domains: `database/`, `builder/`, `automation/`, `dashboard/`, `integrations/`. `contrib/database/data_export/` owns the scheduled Parquet (datalake) table exports: field-type column mapping, the writer, schedules, watermarks and run history.
- `src/baserow/api/` — DRF serializers, views, URL routing, error handling.
- `src/baserow/config/` — Django settings, Celery, Gunicorn config.

## Local Contracts

- Package/venv manager is **uv**; the venv lives at repo-root `.venv`. Never call `pip` directly.
- Layered architecture: **model → handler → service → action → API view**. `handler.py` = persistence/domain; `service.py` = permission-aware orchestration; `actions.py` = undoable actions. Follow the existing `contrib/automation/` modules as the modern reference pattern.
- Behavior is wired through **registries** (`baserow.core.registry`) — types register themselves; add new types via the registry, don't hardcode.
- Every model/schema change needs a Django migration; keep migrations forward-compatible.
- Reuse shared pytest **fixtures** (`test_utils/fixtures/`) rather than hand-building objects.
- SSO is env-configured only (`core/sso/oidc/`): `BASEROW_OIDC_PROVIDERS` is the source of truth, parsed and validated at startup, with a database row per provider used purely as an anchor for user linkage. There is no admin UI or API for creating providers.
- **All OIDC access derives from the IdP's client roles** — global staff/superuser, workspace membership, and the granular `core.roles.Role`. A provider that maps any client role refuses a user holding none of them, before any account is provisioned. Keep new access dimensions on that same path rather than adding a parallel source of truth.
- The OIDC callback fails closed unless the `state`, PKCE S256 verifier and nonce match what the login request stored in the session, and the userinfo `sub` equals the ID token's. `require_verified_email` (default true) refuses identities whose `email_verified` is not `true`, since accounts are linked by email. Keep these checks when touching `core/sso/oidc/handler.py`.
- An existing account refused by the different-provider guard is linked only through `core/sso/oidc/linking.py` (per-provider opt-in `link_existing_accounts`, IdP `email_verified` must be `true`, never staff/superuser) or the operator's `link_oidc_account` management command. Keep the guard in `auth_provider_types.py` intact; don't widen auto-linking to privileged accounts.
- SSO sessions are bounded by the provider's `session_lifetime_minutes` (default 480): the refresh token issued on callback gets that lifetime and refreshing never re-issues it, so a client role removed in the IdP stops applying once the user must sign in again.
- `core/sso/oidc/config.py` and `core/roles/config.py` are imported from `config/settings/base.py` while settings are still evaluating. Keep them import-light (stdlib + `django.core.exceptions`); never import models or third-party clients there.
- `BASEROW_ROLES` declares workspace roles; they are reconciled into `core.Role` rows by `sync_declared_roles` on `post_migrate` and by the `sync_roles` management command. Roles no longer declared are left alone, since members may still be assigned to them.
- External data destinations (S3, Azure Blob, filesystem) are env-configured only (`core/data_destinations/`): `BASEROW_DATA_DESTINATIONS` is parsed at startup and holds every credential. Models and API payloads reference a destination by `name` and must never persist or return its credentials or location. `core/data_destinations/config.py` is imported from settings, so it follows the same import-light rule as the OIDC config below.
- Backups shipped to a destination (`core/backups/destination.py`) write the archive first and its `.zip.json` sidecar last; the sidecar is the completion marker and the only thing listing and remote retention trust. A restore verifies the archive's sha256 against the sidecar. Trusting a remote backup's signing key stays staff-only and opt-in per destination (`allow_trust_public_key`), and the key inside the archive must match the sidecar's.
- Datalake table exports publish part files, then `_manifest.json`, then `_SUCCESS`; a table's watermark only advances after `_SUCCESS` is written. Password and form edit-link fields are never exported, and new field types fall back to a JSON column unless they register a mapper in `data_export/parquet/types.py`. Exports run with the permissions of the schedule's user, re-checked on every run.
- Any code that trashes, restores or bulk-updates rows must bump `updated_on` (`QuerySet.update()` and `save(update_fields=...)` skip `auto_now`); incremental datalake exports select changed rows by `updated_on` and would otherwise miss them.
- Keep `SsoErrorCode` (`core/sso/utils.py`) in sync with the `loginError` keys in `web-frontend/modules/core/locales/en.json`.

## Work Guidance

- Run backend tasks via `just backend <recipe>` (aliases `just b …`): `check`/`lint`, `fix`/`format`, `test`, `run-dev-server`.
- Lint/format is **ruff** (`just b lint` / `just b fix`); types via mypy (`mypy.ini`).
- Prefer the relevant project skills for structured work: `manage-backend-layers`, `baserow-registry`, `manage-permissions`, `create-update-service`, `runtime-formulas`, `write-backend-unit-test`, `add-django-config-env-var`.
- Add a changelog entry for user-facing changes (`just changelog add`).

## Verification

- Tests: `just backend test` (pytest, config in `pytest.ini`; supports `PYTEST_SPLITS`/`PYTEST_EXTRA_ARGS`).
- Lint: `just backend lint`. Both must pass before commit (also enforced by pre-commit).

## Child DOX Index

No child AGENTS.md yet. `core/` and each `contrib/` domain are documented via project skills (`.agents/skills/`); add a child here only if a domain grows its own durable, skill-independent contract.
