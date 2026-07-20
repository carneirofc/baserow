@AGENTS.md

## Skills

`.claude/skills` is a symlink to `.agents/skills`, the canonical location for project skills. Both paths resolve to the same directory.

## Agent skills

### Issue tracker

Issues live as GitHub issues on the repo's remote, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its name (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
