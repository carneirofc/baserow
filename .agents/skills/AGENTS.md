# .agents/skills

## Purpose

Canonical home for this project's agent skills — packaged, reusable procedures for recurring Baserow tasks (backend layers, registries, permissions, services, formulas, changelog, tests, etc.).

## Ownership

Owns every skill directory here. `.claude/skills` is a symlink to this folder, so both paths resolve to the same skills. Each skill is a directory containing a `SKILL.md` (with `name`/`description` frontmatter) plus optional supporting assets (e.g. an `agents/` folder).

## Local Contracts

- One directory per skill; the directory name is the invocation name and must match `SKILL.md`'s `name` frontmatter.
- `SKILL.md` frontmatter needs a `name` and a `description` whose trigger phrasing tells agents when to reach for it.
- Skills describe **project-specific** procedures; keep them in sync with the code paths they reference (e.g. `contrib/automation/` as the modern backend pattern).

## Work Guidance

- Add a skill when a multi-step Baserow task recurs and spans several files/layers; update the relevant skill when its referenced paths or steps change.

## Verification

None wired; skills are prose procedures validated by use.

## Child DOX Index

None. Individual skill folders are self-describing via their `SKILL.md` and are not separate DOX boundaries.
