---
name: repo-fetch
description: Use automatically when a task needs a local checkout of a GitHub repository at a specific branch, tag, or commit — e.g. "grab upstream at v1.2.0", "check out that library's source", "get the code from <github url>", or before running several searches against another repo. Delegates to the repo-reader subagent, which clones into a local cache and returns the path and resolved SHA.
context: fork
agent: repo-reader
model: sonnet
effort: medium
argument-hint: <owner/repo|url> [branch|tag|sha]
---

# Repo fetch

Request: $ARGUMENTS

Follow your repo-reader fetch procedure: normalize the repo and ref (default branch if none), create or update the cached checkout, and resolve the commit SHA. Return only the `Source` section (repo, ref, full SHA, local path) plus a one-line note on whether the checkout was created, updated, or reused. Do not write inside the caller's project.
