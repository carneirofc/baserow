# docs

## Purpose

Project documentation: architecture and technical references, installation/deployment guides, development workflow, agent conventions, and decision records.

## Ownership

Owns everything under `docs/`. Notable subtrees:

- `agents/` — how agents operate in this repo: `issue-tracker.md`, `triage-labels.md`, `domain.md`.
- `adr/` — Architecture Decision Records (numbered `NNN-*.md`).
- `development/`, `technical/`, `patterns/`, `installation/`, `testing/`, `runbooks/`, `tutorials/`, `apis/`, `plugins/` — topic guides.
- `index.md` — docs entry point.

## Local Contracts

- ADRs are append-mostly and numbered; when a change contradicts an existing ADR, surface the conflict rather than silently overriding it (see `agents/domain.md`).
- Keep docs current with the FOSS fork: no pointers/branding tying back to Baserow B.V.
- Docs are Markdown; match the surrounding file's structure and heading style.

## Work Guidance

- Update the doc nearest the change; add a new ADR under `adr/` for durable architectural decisions.
- The `research` and `domain-modeling` skills write their outputs here.

## Verification

None wired.

## Child DOX Index

None.
