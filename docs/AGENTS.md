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
- `docs/` is published as a hosted site (`https://carneirofc.github.io/baserow/`) via `mkdocs.yml` (repo root) + `.github/workflows/docs.yml`, which builds with MkDocs Material and deploys to `gh-pages` on push to `develop`. New top-level guide files must be added to `mkdocs.yml`'s `nav` or they won't appear on the site (they still exist as plain files). `agents/` and `AGENTS.md` are intentionally excluded from `nav` — agent-internal, not user docs.

## Work Guidance

- Update the doc nearest the change; add a new ADR under `adr/` for durable architectural decisions.
- The `research` and `domain-modeling` skills write their outputs here.
- When adding a new guide file, add it to `mkdocs.yml`'s `nav` in the matching section.

## Verification

- `mkdocs build` should run clean of nav-coverage warnings before committing docs changes. Cross-directory links out of `docs/` (e.g. to `deploy/`, `docker-compose.yaml`) will still warn — those files live outside the site and are expected to only resolve via GitHub source browsing.

## Child DOX Index

None.
