---
name: repo-compare
description: Use automatically when a task asks what changed between two refs of a GitHub repository — e.g. "what changed between v1 and v2", "diff upstream vs our fork", "which commits touched X between these tags", "breaking changes in library L from A to B". Delegates to the repo-reader subagent, which fetches both refs locally and returns a themed change summary with cited files and commits.
context: fork
agent: repo-reader
model: sonnet
effort: medium
argument-hint: <owner/repo> <refA> <refB> [path|topic]
---

# Repo compare

Request: $ARGUMENTS

Follow your repo-reader compare procedure: fetch both refs into the shared compare clone, then use `git diff --stat`, focused `git diff`, and `git log <A>..<B>` (scoped to the path or topic if given). Return the output format with Source listing both refs and SHAs, and Findings grouped by theme with cited files and commits. Do not write inside the caller's project.
