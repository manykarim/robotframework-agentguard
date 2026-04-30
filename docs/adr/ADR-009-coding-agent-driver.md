# ADR-009: Coding Agent Driver Pattern

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: CodingAgent

## Context

`agentguard` must drive Claude Code, Codex CLI, GitHub Copilot CLI, Aider, OpenCode, Cline, and Continue from Robot Framework keywords. Each CLI has a different invocation signature, prompt mechanism, session-log format, working-directory convention, and exit-code policy (research §4.4, §7.2). Session logs land in different places: `~/.claude/projects/<project>/<session>.jsonl` for Claude Code, `~/.codex/sessions/` for Codex CLI, `.aider.chat.history.md` + `.aider.input.history` for Aider, `~/.opencode/sessions/` for OpenCode, `.cline/` and `.continue/` workspace directories for Cline/Continue.

Adding a new agent must not require rewriting the metric calculators (ADR-010). The cleanest separation is a `CodingAgentDriver` per CLI that subprocesses the agent, captures the JSONL session log, and **normalises** it into a single canonical `Session` schema. Optional LiteLLM Gateway proxy (ADR-001) gives uniform token/cost capture even when the agent talks to its own backend.

## Decision

Define `CodingAgentDriver` as an abstract interface with concrete subclasses `ClaudeCodeDriver`, `CodexDriver`, `CopilotCLIDriver`, `AiderDriver`, `OpenCodeDriver`, `ClineDriver`, `ContinueDriver`. Each driver: (1) spawns the CLI as a subprocess in a configurable cwd; (2) pipes the prompt or attaches `--prompt-file`; (3) captures the JSONL session-log path; (4) normalises into the canonical `Session` schema (ADR-010); (5) optionally proxies via LiteLLM Gateway for token/cost capture.

## Rationale

- Subprocess + JSONL capture is the only pattern that works across all seven CLIs without privileged integrations.
- Canonical normalisation localises agent-specific quirks to one file each — the metric calculators stay agent-agnostic.
- LiteLLM Gateway proxying solves the "Codex talks to OpenAI directly" cost-capture problem.
- Adding a new agent (e.g., Sourcegraph Amp) becomes "write a parser, list working-dir conventions" — no metric code changes.

## Consequences

- **Positive**: One assertion API across all coding agents; new agents added by writing a single parser; cost capture uniform via LiteLLM Gateway.
- **Negative**: Subprocess management is OS-sensitive (Windows vs. POSIX path handling); JSONL formats change between CLI versions and require driver-version pinning.
- **Neutral**: Driver subclasses must stay thin (≤300 LoC) to avoid drift.

## Alternatives Considered

- **Option A — Embed each agent's library directly in-process**: rejected, most don't expose a library API and embedding voids the "drive the real CLI" guarantee.
- **Option B — Test only Claude Code**: rejected, defeats the cross-vendor portability promise of `agentguard`.
- **Option C — HTTP/REST shim per agent**: rejected, requires each agent to ship a server; reality is they ship CLIs.

## Related ADRs

- ADR-001 (LiteLLM Gateway used for proxy mode)
- ADR-010 (canonical `Session` schema is the consumer of driver output)
- ADR-013 (Drivers run inside sandbox when `--allow-code-execution` is set)
- ADR-014 (Driver versions pinned alongside agent CLI versions)
