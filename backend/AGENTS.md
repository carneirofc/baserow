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
- **The IdP only defines global profiles** through client roles: `user_roles` (may sign in), `staff_roles`, `superuser_roles`. A provider that maps any client role refuses a user holding none of them, before any account is provisioned. Workspace membership, teams and database/table access are managed in the app only — never add workspace-scoped IdP mappings (workspace ids change constantly); `workspace_mappings`, `team_mappings` and `strict_membership` are refused at startup.
- The OIDC callback fails closed unless the `state`, PKCE S256 verifier and nonce match what the login request stored in the session, and the userinfo `sub` equals the ID token's. `require_verified_email` (default true) refuses identities whose `email_verified` is not `true`, since accounts are linked by email. Keep these checks when touching `core/sso/oidc/handler.py`.
- An existing account refused by the different-provider guard is linked only through `core/sso/oidc/linking.py` (per-provider opt-in `link_existing_accounts`, IdP `email_verified` must be `true`, never staff/superuser) or the operator's `link_oidc_account` management command. Keep the guard in `auth_provider_types.py` intact; don't widen auto-linking to privileged accounts.
- SSO sessions are bounded by the provider's `session_lifetime_minutes` (default 480): the refresh token issued on callback gets that lifetime and refreshing never re-issues it, so a client role removed in the IdP stops applying once the user must sign in again.
- `core/sso/oidc/config.py` and `core/roles/config.py` are imported from `config/settings/base.py` while settings are still evaluating. Keep them import-light (stdlib + `django.core.exceptions`); never import models or third-party clients there.
- In-app database access is owned by `contrib/database/access/`: `DatabaseAccessGrant` gives a member or a `core.teams.Team` a level (`none`/`viewer`/`editor`/`builder`) on the workspace default, a database or a table. For a non-admin member the most specific scope with a grant decides (table → database → workspace; direct user grant beats team grants; highest team level wins); no grant passes through to `basic` (full member access). `database_access` sits right after `member` in `PERMISSION_MANAGERS`. `builder` is every database-family operation, so new operations are builder-only until listed in `access/levels.py`. Its `filter_queryset` must keep excluding exactly what its checks deny (parity test in `tests/.../database/access/`). Its denials are `PermissionDenied` subclasses, because websocket page subscriptions and other callers only catch `PermissionDenied`; a bare `PermissionException` there raises instead of refusing.
- Workspace membership only comes from admins adding existing users (`workspace.add_workspace_users`, candidate search needs at least 3 characters and never lists deactivated or to-be-deleted accounts); there are no workspace invitations, invite emails or invite-token signups — don't reintroduce them. Admins also manage teams (`core/teams/`) and grants; staff manage grants of any workspace.
- `CreateUserActionType.Params.with_invitation_token` stays only so stored params of older actions still deserialize (`ActionType` rebuilds `Params(**params)`); never remove a `Params` field of a registered action type.
- `StaffBypassPermissionManagerType` (`core/permission_manager.py`, type `staff_bypass`, positioned right after `staff` and before `member` in `PERMISSION_MANAGERS`) grants staff an operation on any workspace regardless of membership, for a short list in `STAFF_BYPASS_OPERATIONS` (currently the backup/export/restore operations used by `/api/admin/backups/`). Unlike `StaffOnlyPermissionManagerType`, it never denies — for a non-staff actor or an unlisted operation it leaves the check undetermined so `member` still decides normally. Add an operation here, never to `StaffOnlyPermissionManagerType.STAFF_ONLY_OPERATIONS`, when staff need cross-workspace access to something regular members can already do on their own workspace; the latter denies every non-staff actor outright.
- `core/audit_log/` is a permanent, staff-only audit trail sourced from the `action_done` signal (`core/action/signals.py`) plus two explicit hooks for sign-out and failed sign-in (Baserow's auth is JWT, so Django's session login signals never fire). It is a separate table from `core.action.Action` and must never be touched by `core.action.tasks.cleanup_old_actions` or any other purge task. A new `log_auth_event` caller must also be listed in `AUTH_EVENT_TYPES` (`core/audit_log/models.py`), which is what `/api/admin/audit-log/filter-options/` adds to `action_type_registry.get_types()`. Because the table is permanent and unbounded, those filter options are derived from the registry and never from a `DISTINCT` over the entries.
- `FilterableViewMixin.apply_filters` (`api/mixins.py`) treats a blank filter as an absent one: it applies an exact lookup per filter, so `?x=` would otherwise filter on the empty string. Keep the `(None, "")` check rather than a falsiness test, so a meaningful `"0"` still filters.
- External data destinations (S3, Azure Blob, filesystem) are env-configured only (`core/data_destinations/`): `BASEROW_DATA_DESTINATIONS` is parsed at startup and holds every credential. Models and API payloads reference a destination by `name` and must never persist or return its credentials or location. `core/data_destinations/config.py` is imported from settings, so it follows the same import-light rule as the OIDC config below.
- Backups shipped to a destination (`core/backups/destination.py`) write the archive first and its `.zip.json` sidecar last; the sidecar is the completion marker and the only thing listing and remote retention trust. A restore verifies the archive's sha256 against the sidecar. Trusting a remote backup's signing key stays staff-only and opt-in per destination (`allow_trust_public_key`), and the key inside the archive must match the sidecar's.
- Datalake table exports publish part files, then `_manifest.json`, then `_SUCCESS`; a table's watermark only advances after `_SUCCESS` is written. Password and form edit-link fields are never exported, and new field types fall back to a JSON column unless they register a mapper in `data_export/parquet/types.py`. Exports run with the permissions of the schedule's user, re-checked on every run.
- Any code that trashes, restores or bulk-updates rows must bump `updated_on` (`QuerySet.update()` and `save(update_fields=...)` skip `auto_now`); incremental datalake exports select changed rows by `updated_on` and would otherwise miss them.
- File imports into an existing table (modes `insert`/`upsert`/`update`/`replace`, multi-field AND matching, `delete_unmatched`) are planned only by `contrib/database/rows/import_planner.py`. The import (`RowHandler.import_rows_with_result`) and the preview endpoint (`rows/import_preview.py`) both consume that plan, so never compute import changes elsewhere. Ambiguous match keys refuse the import unless `allow_ambiguous_matches`; matched rows without changes are never written.
- `Table.require_edit_confirmation` ("protected editing", toggled via `UpdateTableEditConfirmationActionType`) is a web-frontend safeguard only: never enforce it in handlers, services or API views, so API tokens, integrations and automations keep writing directly. It must round-trip through table export/import. Row changes on protected tables are audited by the regular row actions through `core/audit_log/`; don't add a parallel log.
- Keep `SsoErrorCode` (`core/sso/utils.py`) in sync with the `loginError` keys in `web-frontend/modules/core/locales/en.json`.

## Work Guidance

- Run backend tasks via `just backend <recipe>` (aliases `just b …`): `check`/`lint`, `fix`/`format`, `test`, `run-dev-server`.
- Lint/format is **ruff** (`just b lint` / `just b fix`); types via mypy (`mypy.ini`).
- Prefer the relevant project skills for structured work: `manage-backend-layers`, `baserow-registry`, `manage-permissions`, `create-update-service`, `runtime-formulas`, `write-backend-unit-test`, `add-django-config-env-var`. Locate files to change first with `find-change-candidates`.
- Add a changelog entry for user-facing changes (`just changelog add`).

## Verification

- Tests: `just backend test` (pytest, config in `pytest.ini`; supports `PYTEST_SPLITS`/`PYTEST_EXTRA_ARGS`).
- Lint: `just backend lint`. Both must pass before commit (also enforced by pre-commit).

## Child DOX Index

No child AGENTS.md yet. `core/` and each `contrib/` domain are documented via project skills (`.agents/skills/`); add a child here only if a domain grows its own durable, skill-independent contract.
