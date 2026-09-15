---
name: ci-failure-report
description: Use automatically when a GitHub Actions run, workflow, or PR check has failed and the cause is needed — e.g. "why did CI fail", "the build is red", "PR checks failing", "debug this workflow run", a failing run URL, or a failed status reported by ci-status. Delegates to the ci-inspector subagent, which returns failing jobs/steps, error excerpts, likely cause, regression window, and local repro commands.
context: fork
agent: ci-inspector
model: sonnet
effort: medium
argument-hint: [run-id|run-url|pr#|branch|sha]
---

# CI failure report

Request: $ARGUMENTS

Follow your ci-inspector procedure: resolve the target (default: most recent failed run for the current branch), run the full failure drill-down (saved logs, error signatures, artifacts if needed, flakiness hints), link failures to workflow steps and local `just` reproducers, and compute the regression window. Return the full output format. Read-only.
