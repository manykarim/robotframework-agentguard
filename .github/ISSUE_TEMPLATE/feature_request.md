---
name: Feature request
about: Propose a new keyword, sub-library, or driver for AgentGuard
title: "[feat] "
labels: ["enhancement"]
assignees: []
---

## Problem
<!-- Which agentic-system testing scenario is currently painful or impossible? -->

## Proposed keyword / API

```robot
*** Test Cases ***
Proposed
    Some New Keyword    arg=value
```

## Bounded context

Which DDD context does this belong to (`docs/ddd/bounded-contexts.md`)?

- [ ] Provider
- [ ] MCP
- [ ] Skills
- [ ] Hooks
- [ ] SubAgents
- [ ] CodingAgent
- [ ] Statistics
- [ ] Judge
- [ ] Security
- [ ] Telemetry
- [ ] BehavioralMetrics
- [ ] ToolCallCorrectness

## Phase

- [ ] Phase 1 — MCP + Skills + Stats + Judge
- [ ] Phase 2 — Hooks + SubAgents + Sandbox
- [ ] Phase 3 — Coding-agent harness + #42796
- [ ] Phase 4 — OSS hardening + RuFlo integrations

## Related ADR / research

<!-- Link to docs/adr/ or docs/research/research.md sections, if any. -->

## Acceptance criteria

- [ ] Keyword exposed via the relevant `*Keywords` class
- [ ] Default-offline (no API key required) **or** clearly marked `live`
- [ ] Unit tests under `tests/unit/<module>/`
- [ ] Acceptance suite under `tests/acceptance/`
- [ ] Documented in `docs/api/` (libdoc) and `examples/`
