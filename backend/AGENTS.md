# backend

## Purpose

Django backend for Baserow: REST API, real-time WebSocket layer, Celery workers, and the domain logic behind databases, the Application Builder, Automation, Dashboards, and integrations.

## Ownership

Owns everything under `backend/`: `src/baserow/` (source), `tests/` (pytest suite), `Dockerfile`, `pyproject.toml`, `pytest.ini`, `mypy.ini`, `justfile`, and packaging.

- `src/baserow/core/` — cross-cutting platform: registries, permissions, jobs, import/export, backups and backup schedules, contents, API clients, auth, formulas, notifications, MCP.
- `src/baserow/contrib/` — feature domains: `database/`, `builder/`, `automation/`, `dashboard/`, `integrations/`.
- `src/baserow/api/` — DRF serializers, views, URL routing, error handling.
- `src/baserow/config/` — Django settings, Celery, Gunicorn config.

## Local Contracts

- Package/venv manager is **uv**; the venv lives at repo-root `.venv`. Never call `pip` directly.
- Layered architecture: **model → handler → service → action → API view**. `handler.py` = persistence/domain; `service.py` = permission-aware orchestration; `actions.py` = undoable actions. Follow the existing `contrib/automation/` modules as the modern reference pattern.
- Behavior is wired through **registries** (`baserow.core.registry`) — types register themselves; add new types via the registry, don't hardcode.
- Every model/schema change needs a Django migration; keep migrations forward-compatible.
- Reuse shared pytest **fixtures** (`test_utils/fixtures/`) rather than hand-building objects.

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
