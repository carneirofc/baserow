---
name: repo-search
description: Use automatically when answering requires reading or searching another GitHub repository or ref — e.g. "how does upstream/library X implement Y", "what does version Z of repo R do", "where is this configured in <owner/repo>", "look at the code in <github url>", "how does upstream Baserow handle this". Delegates to the repo-reader subagent, which checks out the ref locally and returns cited findings.
context: fork
agent: repo-reader
model: sonnet
effort: medium
argument-hint: <owner/repo>[@ref] <question>
---

# Repo search

Request: $ARGUMENTS

Follow your repo-reader procedure: fetch (or reuse) the cached checkout for the repo and ref (default branch if none), then search and read it to answer the question. Return the full output format (Source, Findings with `path:line` citations, Related files, Open questions). Do not write inside the caller's project.
