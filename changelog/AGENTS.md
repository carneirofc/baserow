# changelog

## Purpose

Conflict-free changelog generator: each change is a standalone JSON entry so parallel branches never collide on a shared `changelog.md`.

## Ownership

Owns everything under `changelog/`: `src/` (generator), `entries/` (per-change JSON, with an `unreleased/` staging area), `releases.json`, `conftest.py`, `tests/`, and `README.md`. The generated root `changelog.md` is the published output.

## Local Contracts

- All commands run from the repo root via `just changelog <cmd>` — never edit `changelog.md` by hand.
- `just changelog add` creates an entry in `entries/unreleased/` as a `.json` file (editable directly).
- `just changelog release <name>` moves unreleased entries into a release folder, appends to `releases.json`, and regenerates `changelog.md`.

## Work Guidance

- Every user-facing or behavioral change gets an entry; use the `create-changelog` skill to classify domain/type and write the message.

## Verification

- `just changelog-test` runs the generator's own test suite (`changelog/tests/`).

## Child DOX Index

None.
