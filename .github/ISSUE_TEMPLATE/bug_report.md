---
name: Bug report
about: Report a defect in `robotframework-agentguard`
title: "[bug] "
labels: ["bug"]
assignees: []
---

## Summary
<!-- One sentence: what is broken and which keyword / module is affected. -->

## Reproduction

```robot
*** Settings ***
Library    AgentGuard

*** Test Cases ***
Repro
    # Minimal failing example
```

Or, for a Python-side bug, paste a short pytest/script.

## Expected behavior
<!-- What did you expect to happen? -->

## Actual behavior
<!-- What actually happened? Include traceback / Robot log excerpt. -->

## Environment

Run `uv run agentguard doctor` and paste the table here:

```
$ uv run agentguard doctor
...
```

- AgentGuard version: `uv run agentguard version`
- Python version:
- OS / runner:
- Provider / model:

## Logs / artifacts
<!-- Attach `output.xml`, `log.html`, or relevant JSONL. Redact API keys. -->

## Additional context
<!-- Links to related issues, ADRs, or research notes. -->
