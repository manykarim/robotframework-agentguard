# ADR-007: Hook Test Harness

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: Hooks

## Context

Claude Code's hooks reference defines 12 lifecycle events (`UserPromptSubmit`, `UserPromptExpansion`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `Notification`, `Stop`, `SubagentStop`, `PreCompact`, `SessionStart`, `ConfigChange`) invoked via four handler types (`command`, `http`, `prompt`, `agent`). Communication is JSON-on-stdin / JSON-or-text-on-stdout with **exit code 2 = block** semantics. Decision objects carry `{decision, reason, permissionDecision}` (research §2.3).

There is no widely adopted automated test harness for hooks today. Existing projects (`disler/claude-code-hooks-mastery`, GitButler `but claude pre-tool`) hand-validate behavior. This is the largest gap in the ecosystem.

A hook is, fundamentally, a deterministic JSON-in/JSON-out process with an exit code — exactly the kind of artifact keyword-driven testing excels at. Loop safety matters: a buggy `Stop` hook can recurse infinitely if it doesn't honour `stop_hook_active`.

## Decision

Build `HooksKeywords` sub-library exposing: `Synthesize Hook Input` (canonical JSON envelope per event), `Run Hook Command | Run Hook HTTP | Run Hook Prompt | Run Hook Agent` (the four handler types), and decision assertions `Hook Should Block | Hook Should Allow | Hook Should Inject Context | Hook Decision Should Be | Hook Should Modify Tool Input To`. Cover all 12 lifecycle events. Detect `stop_hook_active` infinite-loop antipatterns and fail the test if observed.

## Rationale

- Fills the largest documented ecosystem gap (research §2.3).
- JSON-in/exit-code-out maps cleanly onto Robot Framework keyword semantics.
- All four handler types must be supported because real deployments mix them (e.g., shell `command` hooks for fast checks, `http` for centralised policy, `prompt` for Stop-hook reasoning, `agent` for delegated decisions).
- Loop detection is non-negotiable: `stop_hook_active` infinite loops are the dominant Stop-hook bug class.

## Consequences

- **Positive**: First open test harness for hooks; cross-tool compatibility (Claude Code, OpenCode plugin hooks, Cline, Continue, Copilot extension hooks share the same JSON-envelope shape).
- **Negative**: HTTP and `agent` handlers introduce network/LLM dependencies into hook tests — must be mockable.
- **Neutral**: Coverage of all 12 events is large up-front work; can be phased (PreToolUse / PostToolUse / Stop first, others second).

## Alternatives Considered

- **Option A — Test hooks as opaque shell scripts only**: rejected, ignores `http`/`prompt`/`agent` handler types.
- **Option B — Wrap a vendor-specific hooks SDK**: rejected, no such SDK exists with cross-tool coverage.
- **Option C — Fuzz hooks with random JSON envelopes**: rejected as primary path; useful as a complementary keyword (`Fuzz Hook With N Inputs`) but not the contract.

## Related ADRs

- ADR-003 (Hooks sub-library composition)
- ADR-013 (Sandbox policy applies if a hook test runs untrusted handlers)
- ADR-017 (RuFlo `hooks_*` tools complement, not replace, this harness)
