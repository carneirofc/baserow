---
name: ci-status
description: Use automatically when CI / GitHub Actions status is relevant — e.g. "is CI green", "did the checks pass", "status of the PR checks", right after `git push` or `gh pr create`, or before declaring work done on a pushed branch. Delegates to the ci-inspector subagent, which returns a status table for the branch, commit, PR, or workflow and drills into any failures.
context: fork
agent: ci-inspector
model: sonnet
effort: medium
argument-hint: [pr#|branch|sha|run-id|workflow] [-R owner/repo]
---

# CI status

Request: $ARGUMENTS

Follow your ci-inspector procedure: resolve the target (default: current branch HEAD of `origin`), list the latest run per workflow (and PR checks when a PR is involved), and return the Target and Status sections. If any run failed, also run the failure drill-down and include Failures, Regression window, and Local repro. Read-only.
