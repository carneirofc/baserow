---
name: find-change-candidates
description: Use automatically before planning or editing any Baserow feature, bug fix, or refactor whose target files are not yet known — also for "which files need to change", "where would X go", "where does X live". Delegates file discovery to the change-scout subagent and returns ranked candidate files.
context: fork
agent: change-scout
model: sonnet
effort: medium
argument-hint: <task description>
---

# Find change candidates

Task: $ARGUMENTS

Follow your change-scout procedure for this task: orient via the AGENTS.md chain and relevant `.agents/skills/`, search the backend layer chain, frontend mirror, tests, and repo couplings, then return the fixed output format (Primary, Secondary / ripple, Reference patterns, Open questions). Do not edit files.
