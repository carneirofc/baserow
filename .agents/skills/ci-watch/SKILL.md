---
name: ci-watch
description: Use automatically when a GitHub Actions run is queued or in progress and its outcome matters — e.g. "wait for CI", "let me know when checks finish", "monitor the pipeline", or after pushing when the next step depends on CI passing. Delegates to the ci-inspector subagent, which watches the run (bounded) and reports the outcome, drilling into failures.
context: fork
agent: ci-inspector
model: sonnet
effort: medium
argument-hint: [run-id|pr#|branch|sha] [-R owner/repo]
---

# CI watch

Request: $ARGUMENTS

Follow your ci-inspector monitoring procedure: resolve the target run(s) (default: in-progress runs for the current branch HEAD), watch with a bounded timeout, then return Target and Status. On failure, include the failure drill-down sections; if still running at the timeout, report current job states and run IDs for re-invocation. Read-only.
