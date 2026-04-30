# Aggregate Design — Four Most Complex Aggregates

For each aggregate: **invariants** (rules the root must enforce), **transactional boundary** (what changes atomically), **identifier strategy**, and **what is loaded eagerly vs. lazily**. Citations point to `docs/research/research.md`.

---

## 1. `Skill` (Skills Context)

The most subtle aggregate because Skills is the largest single user-facing surface (Phase 1, §5) and because it sits behind a Security gate.

### Invariants

- **Frontmatter completeness:** `name` and `description` are mandatory (Agent Skills spec, §2.2). A `Skill` cannot transition out of state `Discovered` without valid frontmatter — invalid frontmatter raises and emits `SkillFailed`.
- **Allowed-tools subset rule:** if `allowed-tools` is present, every tool the grader exposes to the model must be a member; the grader is forbidden from injecting tools outside this set.
- **Security gate first:** a `Skill` cannot transition to `Loaded` until `SecurityPolicy.evaluate(skill)` returns `Allowed`. `SkillDenied` is terminal — no `SkillLoaded` may follow.
- **Single scorecard per (skill, baseline) pair:** producing a `SkillScorecard` is idempotent for a given baseline; re-grading replaces the scorecard atomically with a new aggregate version.
- **Grader determinism boundary:** `runs >= 1`. When `runs > 1`, the scorecard must store the full `Distribution` so Statistics can compute pass@k and CIs (§3.4) — never just the mean.
- **Convention-violation rules are project-scoped:** the rules used to detect `SkillConventionViolationDetected` come from the consuming project's `CLAUDE.md` and must not be embedded in the `Skill` aggregate.

### Transactional Boundary

One `Skill` aggregate is the unit of transaction. A grading run mutates exactly one `Skill` (its `SkillScorecard`); transcripts and judgments are written through it. Cross-skill batch grading is a saga, not a transaction — each `Skill` advances independently and emits its own events.

### Identifier Strategy

Composite identifier: `(install_path, skill_name)` where `install_path` is one of the four standard roots (`.claude/skills/`, `.agents/skills/`, `~/.gemini/.../skills/`, `~/.codex/skills/`) plus an optional marketplace namespace prefix. The composite is hashed to a stable `SkillId` (UUIDv5 with the path namespace) so that re-discovery is deterministic across runs.

### Eager vs. Lazy Loading

- **Eager** on aggregate construction: `SkillFrontmatter`, the file list of `scripts/`, `references/`, `assets/` (sizes only).
- **Lazy:** the contents of any `references/` document, any `assets/` binary, and the `SkillScorecard` history older than the most recent baseline.
- **On grading start:** load the `Rubric` and `EvalPrompt` set into the aggregate scope; release them on `SkillScorecardEmitted`.

---

## 2. `A2ATask` (SubAgents Context)

Lifecycle-rich, externally observable, and the integration point for every multi-agent framework bridge (§2.4, §5 Phase 2, §7.4).

### Invariants

- **Status transitions follow A2A:** `submitted → working → {input-required → working}* → {completed | failed | canceled}`. Any other transition emits `TaskFailed` and locks the aggregate.
- **AgentCard immutability per task:** the `AgentCard` snapshotted at `TaskSubmitted` is the contract for that task — even if the remote agent updates its card mid-run, the in-flight task uses the original.
- **Artifact append-only:** `Artifact`s are appended in arrival order; once `TaskStatus` is terminal, no new artifacts may be appended.
- **Delegation chain integrity:** every entry in the `DelegationChain` references either an MCP `ToolCalled` (vertical, §7.4) or a child `A2ATask` (horizontal). No orphan entries. Cycles are prohibited and detected by hashing `(parent_task_id, child_agent_url, child_skill_name)`.
- **SubagentStop correlation:** if a child task ends and Hooks publishes `SubagentStopOccurred`, the parent task must record it within the same aggregate version — guaranteeing the trajectory match used by ToolCallCorrectness sees a complete chain.
- **Timeout → canceled, not failed:** explicit semantics — a configured `Wait For Task Completion` timeout transitions to `canceled` so reporting can distinguish remote failure from harness give-up.

### Transactional Boundary

One `A2ATask` is the transactional unit. Child tasks (delegations) are **separate aggregates**, referenced by ID — not embedded — to prevent unbounded aggregate growth across deep delegation chains. Cross-task consistency (chain integrity) is reconciled by an event handler in the same context.

### Identifier Strategy

`TaskId` issued by the remote A2A server when present (per A2A protocol). When the server omits one, the harness generates a UUIDv4 prefixed with the `agent_url` host so logs remain greppable across runs.

### Eager vs. Lazy Loading

- **Eager:** `AgentCard` snapshot, current `TaskStatus`, the `DelegationChain` head pointer.
- **Lazy:** the body of each `Artifact` (only the metadata is eager), the full child-task aggregates (loaded on demand for trajectory comparison).

---

## 3. `CodingAgentSession` (CodingAgent Context)

The hardest aggregate to design because it spans process lifecycle, file IO, and an extensible per-CLI parser (§7.2, §5 Phase 3).

### Invariants

- **Driver is fixed at construction:** the `CodingAgentDriver` (`claude-code` | `codex-cli` | `aider` | `opencode` | `cline` | `continue` | `copilot-cli`) is immutable for the life of the aggregate. Switching drivers means a new aggregate.
- **Working directory is sandboxed when required:** if Security policy requires a sandbox, `WorkingDirectory` must resolve inside the active `SandboxBackend` mount; otherwise `SessionStarted` is rejected.
- **Transcript path determined before SessionStarted:** the JSONL path must be either configured or inferred from the driver's known location (`~/.claude/projects/...`, `~/.codex/sessions/`, `.aider.chat.history.md`, `~/.opencode/sessions/`, `.cline/`, `.continue/`) before the CLI is spawned. If the path cannot be determined, the aggregate refuses to start.
- **Normalized schema completeness:** every field of `NormalizedSession` (`messages`, `tool_calls`, `tool_responses`, `thinking_blocks`, `signature_lengths`, `interrupts`, `hook_events`, `usage`) must be present after `TranscriptParsed` — even when empty (`[]` or `0`). Missing fields fail the parse rather than producing a half-populated session that would silently distort BehavioralMetrics.
- **One `SessionEnded` per `SessionStarted`:** even on subprocess crash, the aggregate must emit `SessionEnded` (with `ExitStatus.crashed`) — this guarantees Telemetry sees a closed span and BehavioralMetrics never sees a session in indefinite "open" state.
- **Usage authoritative source:** when the LiteLLM Gateway proxy is enabled (§7.2), Gateway-reported `usage` overrides whatever the JSONL claims. This invariant is enforced inside the aggregate so downstream metrics see one source of truth.

### Transactional Boundary

One run of one CLI is one aggregate. The transaction commits at `TranscriptParsed`. Multi-prompt sessions (a single CLI invocation receiving several prompts) are still one aggregate; the JSONL has them all and parsers split into `messages`. Cross-session comparisons (e.g. baseline drift) go through Statistics on emitted `NormalizedSession` snapshots, not by mutating multiple aggregates.

### Identifier Strategy

`SessionId = (driver, session_id_from_jsonl)`. Each driver is responsible for extracting its native session ID (Claude Code's filename UUID, Codex CLI's session UUID, Aider's chat ID, etc.). When the CLI provides none, fall back to `(driver, sha256(transcript_path + start_timestamp))`.

### Eager vs. Lazy Loading

- **Eager:** `CLICommand`, `WorkingDirectory`, `JSONLTranscript` path metadata, `ExitStatus`, `usage` summary.
- **Lazy:** the parsed `NormalizedSession` itself — parsed on first access by BehavioralMetrics or ToolCallCorrectness, then cached. The raw JSONL lines are streamed (not slurped) for sessions over a configurable size.
- **Released on aggregate close:** the parsed `messages` array is the largest item in memory; release it after `BehavioralReport` is emitted unless explicitly held by Telemetry's report sink.

---

## 4. `BFCLEvaluation` (ToolCallCorrectness Context)

The aggregate behind every BFCL-style assertion — small but with strict matching invariants (§3.1, §6.6).

### Invariants

- **Category-locked at construction:** `Category` (`simple` | `parallel` | `multiple` | `multi-turn` | `decide-not-to-act`) is immutable. The matcher used for each `Sample` is selected by category; mixing categories within a single evaluation is rejected.
- **Matching mode is total:** every `Sample` must produce either `CallMatched` or `CallMismatched` (or, for `decide-not-to-act`, a verdict on whether any tool was called). Skipped samples are treated as failures.
- **AST equivalence is canonical:** argument comparison uses the canonical-AST procedure ported from `inspect_evals/bfcl` — whitespace and key order ignored, but type coercion is *not* applied (string `"1"` ≠ integer `1`). This is locked in code and tested.
- **Trajectory match honors wildcards:** ordered subsequence with optional wildcards (§3.1). Two consecutive wildcards collapse to one. Unbounded wildcards are forbidden in `multi-turn` to avoid false positives in long trajectories.
- **Parallel match uses multiset equality:** for `parallel`, expected and actual are compared as multisets. Argument-AST equality applies per pair.
- **Score reproducibility:** `BFCLScoreComputed` includes the dataset hash and matcher version so re-runs produce byte-identical scores when inputs are identical.

### Transactional Boundary

One `BFCLEvaluation` per run of one dataset against one (consumer-context, model) pair. The transaction commits when `BFCLScoreComputed` is emitted. Per-sample matching events are stored on the aggregate and may be replayed for forensic analysis.

### Identifier Strategy

`EvaluationId = sha256(dataset_id + dataset_version + category + consumer_context + model_id + matcher_version)`. Deterministic so that running the same evaluation twice produces the same ID — useful for caching and for baseline lookup in Statistics.

### Eager vs. Lazy Loading

- **Eager:** `Category`, `Sample` metadata (id, expected-call shape), `MatcherRegistry` reference.
- **Lazy:** the `Sample.prompt` body and any large `tools` JSON Schema — loaded by the consumer (MCP, Skills, or SubAgents) when generating the actual call.
- **On score:** keep per-sample `ASTMatchResult` / `TrajectoryMatchResult` for the duration of the run; persist `BFCLScore` and a digest of mismatches. Full mismatch detail is offloaded to Telemetry as a report artifact rather than retained in the aggregate.
