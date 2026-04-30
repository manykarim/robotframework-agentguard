---
name: clean-skill
description: A minimal, well-formed skill used as the security-scanner happy path.
allowed-tools:
  - Read
  - Grep
publisher: agentguard
signed: true
---

# Clean Skill

This skill performs a read-only summary of a target file and produces a
short structured report. It declares only `Read` and `Grep` (both inside
the default tool allowlist), claims the `agentguard` first-party publisher,
and ships a `signed: true` flag so the Phase-1 signature stub passes.

## Behaviour

1. Read the target file.
2. Search it for the pattern provided in the skill input.
3. Emit a JSON object with `path`, `pattern`, `match_count`.

No code execution, no network egress, no PII.
