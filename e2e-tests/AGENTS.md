# e2e-tests

## Purpose

End-to-end test suite that drives the full stack (backend + frontend + Postgres + Redis) through a real browser with Playwright.

## Ownership

Owns everything under `e2e-tests/`: `tests/` (specs), `pages/` (page objects), `fixtures/`, `client.ts`, `playwright.config.ts`, `justfile`, and the Dockerized service wiring.

## Local Contracts

- Runner is **Playwright** (`playwright.config.ts`); package manager is **yarn**.
- Tests run against **built CI images** (`baserow/backend:ci`, `baserow/web-frontend:ci`) on a dedicated Docker network, not a local dev server.
- Use the **page-object** pattern in `pages/` (e.g. `loginPage.ts`, `baserowPage.ts`) — specs should not select raw DOM ad hoc.
- Fixtures/DB seed live in `fixtures/` (`e2e-db.dump`); restore/dump via the justfile recipes rather than manual SQL.

## Work Guidance

- Run via `just e2e <recipe>`: `build`, `up`, `test`, `down`, or `run` (build + up + test + down end-to-end).
- Local iteration: `run-e2e-tests-locally.sh` and `wait-for-services.sh` bring up and gate on the stack.

## Verification

- `just e2e run` executes the full suite against fresh CI images and tears down. See `README.md` for prerequisites.

## Child DOX Index

None.
