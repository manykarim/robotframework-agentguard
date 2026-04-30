---
name: good-example
description: Demonstrate a minimal valid Agent Skill used by AgentGuard's own tests.
allowed-tools:
  - Read
  - Write
---

# Good Example Skill

This is a fixture skill used by `tests/unit/skills/` and the acceptance suite to
confirm the SKILL.md parser + Inspect AI grader wiring works end-to-end.

## When to use

Use this skill whenever the test harness asks for a representative,
spec-compliant SKILL.md. It declares two `allowed-tools` (`Read`, `Write`) and
ships no scripts/references/assets, exercising the minimum-viable shape.

## Behavior

When prompted, respond with a short Robot Framework keyword stub that reads a
file and writes the upper-cased contents back.
