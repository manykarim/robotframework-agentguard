# Ubiquitous Language — robotframework-agentguard

Every term here is used identically in code, ADRs, tests, docs, and Robot Framework keyword names. Citations point to `docs/research/research.md` sections (§) or to the external standard.

## Skills, Skill Files, Skill Lifecycle

| Term | Definition | Source |
|---|---|---|
| **Skill** | A portable folder loadable by an agent: `SKILL.md` plus optional `scripts/`, `references/`, `assets/`. | Agent Skills spec, §2.2 |
| **SKILL.md** | Markdown entrypoint of a Skill containing YAML frontmatter and human prose. | Agent Skills spec, §2.2 |
| **Skill Frontmatter** | YAML block at top of `SKILL.md` with `name`, `description`, optional `allowed-tools`. | §2.2 |
| **Skill Install Path** | Filesystem location an agent searches for skills (`.claude/skills/`, `.agents/skills/`, `~/.gemini/.../skills/`, `~/.codex/skills/`). | §2.2, §5 Phase 1 |
| **Skill Scorecard** | Per-skill grading record produced by the grader (mirrors `rf-skill-eval` output). | §2.2, §5 Phase 1 |
| **rf-skill-eval** | Existing Claude-Code-specific harness in `manykarim/robotframework-agentskills` we are generalizing. | §2.2 |
| **Allowed Tools** | Frontmatter list constraining which tools the agent may use while a skill is active. | Agent Skills spec, §2.2 |

## MCP — Model Context Protocol

| Term | Definition | Source |
|---|---|---|
| **MCP Server** | Process exposing tools/resources/prompts over JSON-RPC. | MCP spec, §2.1 |
| **MCP Transport** | Wire format used to talk to a server: `stdio`, `sse`, `streamable-http`, `in-memory`. | §4.4, §7.3 |
| **In-Memory Transport** | FastMCP pattern: bind `Client(server)` in-process for deterministic unit tests. | §2.1, §7.3 |
| **MCP Inspector** | Official browser+CLI debugger (`@modelcontextprotocol/inspector`). | §2.1 |
| **MCP Tool** | Callable function exposed by a server with a JSON Schema. | MCP spec |
| **MCP Resource** | URI-addressable, typed payload exposed by a server. | MCP spec |
| **MCP Prompt** | Server-defined reusable prompt template. | MCP spec |
| **Tool Call** | A single invocation of a tool with arguments, capturing the request and response. | §3.1 |
| **Capabilities** | The `tools`, `resources`, `prompts` set advertised by a server. | §6.1 |

## Hooks

| Term | Definition | Source |
|---|---|---|
| **Hook** | A handler invoked at one of 12 lifecycle events by the agent runtime. | §2.3 |
| **Hook Event** | One of `UserPromptSubmit`, `UserPromptExpansion`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `Notification`, `Stop`, `SubagentStop`, `PreCompact`, `SessionStart`, `ConfigChange`. | §2.3 |
| **Hook Handler Type** | One of `command`, `http`, `prompt`, `agent`. | §2.3 |
| **Hook Envelope** | Canonical stdin JSON: `tool_name`, `tool_input`, `tool_response`, `transcript_path`, `cwd`, `session_id`, `stop_hook_active`. | §5 Phase 2 |
| **Hook Decision** | `{"decision": "block"\|"allow"\|"escalate", "reason": ...}` plus optional `permissionDecision`. | §2.3 |
| **Block (exit 2)** | Hook semantics: `PreToolUse` exit 2 stops a tool; `Stop` exit 2 forces the agent to keep working. | §2.3 |
| **stop_hook_active** | Envelope flag preventing infinite Stop loops. | §2.3, §5 Phase 2 |
| **Stop-Hook Violation** | Trigger of a Stop-phrase guard pattern (ownership-dodging, premature-stopping, permission-seeking, known-limitation labeling, session-length excuses). | §2.6 |

## SubAgents and A2A

| Term | Definition | Source |
|---|---|---|
| **SubAgent** | An agent invoked by another agent to handle a delegated task. | §2.4 |
| **A2A** | Agent2Agent protocol — vendor-neutral JSON-RPC + SSE for inter-agent calls (Linux Foundation, 1.0 in 2026). | §2.4 |
| **AgentCard** | Discovery document at `.well-known/agent.json` describing an agent's skills, auth, endpoints. | §2.4, §6.4 |
| **A2A Task** | Lifecycle-managed unit of work submitted to a remote agent. | §2.4 |
| **Task Status** | One of `submitted`, `working`, `input-required`, `completed`, `failed`, `canceled`. | A2A spec |
| **Artifact** | Typed output produced by an A2A Task. | §2.4, §6.4 |
| **Delegation Chain** | Ordered sequence of agent-to-agent task spawns observed during execution. | §5 Phase 2 |
| **SubagentStop** | Hook event fired when a delegated sub-agent terminates. | §2.4 |

## Coding Agents and Sessions

| Term | Definition | Source |
|---|---|---|
| **Coding Agent** | A CLI-driven agent that edits code (Claude Code, Codex CLI, Aider, OpenCode, Cline, Continue, Copilot CLI). | §2.5, §7.2 |
| **CodingAgentDriver** | Adapter that subprocesses a coding-agent CLI and normalizes its session log. | §7.2 |
| **JSONL Transcript** | Per-session newline-delimited JSON file written by a coding agent. | §7.2 |
| **Session** | Normalized schema: `messages`, `tool_calls`, `tool_responses`, `thinking_blocks`, `signature_lengths`, `interrupts`, `hook_events`, `usage`. | §7.2 |
| **Trajectory** | Ordered tool-call sequence inside a Session. | §3.1, §5 Phase 2 |
| **Reasoning Loop** | Self-correction phrase ("oh wait", "actually", "let me reconsider") in the transcript. | §2.6 |
| **Convention Violation** | Edit that violates `CLAUDE.md` rules (abbreviated names, banned phrasing, wrong cleanup). | §2.6 |

## Behavioral Metrics — Issue #42796

| Term | Definition | Source |
|---|---|---|
| **Read:Edit Ratio** | File-reads divided by file-edits in a Session (baseline 6.6, degraded 2.0). | §2.6, §3.3 |
| **Edits Without Prior Read** | Percent of edits whose target file is not in recent read history. | §2.6 |
| **User Interrupt** | `[Request interrupted by user]` event in the transcript. | §2.6 |
| **Self-Admitted Error** | Unprompted "you're right, that was lazy/wrong/sloppy" admission. | §2.6 |
| **Write-vs-Edit Ratio (Write Mutation Ratio)** | Percent of mutations done as full-file Write instead of surgical Edit. | §2.6 |
| **Token Efficiency** | Output tokens or API requests per equivalent user prompt. | §2.6 |
| **First-Run Test Pass Rate** | pass@1 on the project's pre-existing test suite (Aider's "plausible solution"). | §2.5, §2.6 |

## Tool-Call Correctness — BFCL

| Term | Definition | Source |
|---|---|---|
| **BFCL** | Berkeley Function Calling Leaderboard — AST-match-based tool-call evaluation. | §2.2, §3.1 |
| **AST Match** | Tool-call equality ignoring whitespace/order, comparing argument ASTs. | §3.1 |
| **Trajectory Match** | Ordered subsequence comparison of expected vs actual tool calls (with optional wildcards). | §3.1 |
| **Decide-Not-To-Act** | Ground-truth case in which the correct behavior is to call no tool. | §3.1 |
| **Parallel Tool Calls** | Multiple tools invoked in a single turn — multiset equality applies. | §3.1 |

## Statistics, Non-Determinism, Judge

| Term | Definition | Source |
|---|---|---|
| **Mann-Whitney U / Wilcoxon** | Non-parametric stochastic-dominance test. | §2.7 |
| **Cliff's delta** | Effect size in `[-1, 1]`. | §2.7 |
| **Vargha-Delaney A** | Effect size in `[0, 1]`. | §2.7 |
| **Bootstrap CI** | Resampling-based confidence interval. | §2.7 |
| **TARr@N / TARa@N** | Total Agreement Rate (raw / parsed) over N runs. | §2.7 |
| **pass@k** | Probability ≥1 of k samples passes (HumanEval convention). | §2.7 |
| **Distribution** | Sample of metric values across repeated runs. | §3.4 |
| **Effect Size** | Magnitude of a difference, distinct from a p-value. | §2.7 |
| **LLM-as-Judge** | Classification-based grading by an LLM, validated against human labels first. | §2.7, §8.1 |
| **Rubric** | Human-authored grading criteria the judge applies. | §3.4, §6.2 |
| **Judgment** | A single Rubric-scored verdict on one Sample. | §3.4 |
| **Calibration** | Inter-rater agreement (Cohen's κ / Krippendorff's α) judge-vs-human. | §8.1 |

## Inspect AI Vocabulary (Adopted)

| Term | Definition | Source |
|---|---|---|
| **Task** | An evaluation: dataset + Solver + Scorer. | §2.2 |
| **Solver** | The agent (or chain) that produces an answer. | §2.2 |
| **Scorer** | The grading function. | §2.2 |
| **Sample** | One dataset row (input + expected output). | §2.2 |

## Security and Supply Chain

| Term | Definition | Source |
|---|---|---|
| **ToxicSkills** | Snyk study (April 2026) — 36% of community skills had security flaws. | §8.3 |
| **ClawHavoc** | Coordinated malicious-skill campaign distributing AMOS infostealers. | §8.3 |
| **Sandbox Backend** | Isolated execution environment (Docker, K8s, Proxmox) for code execution. | §8.2 |
| **Skill Signature** | Cryptographic signature on a Skill bundle proving provenance. | §8.3 |
| **Allowlist** | Explicit set of skills/tools permitted to run. | §8.3 |
| **PII Detection** | Pre-flight scan for personally identifiable information in prompts/transcripts. | aidefence integration |
| **Prompt Injection** | Adversarial input intended to subvert agent instructions. | §8.3 |
| **Tool Approval** | Human-in-the-loop gate before sensitive tool execution (Inspect AI pattern). | §4.1, §8 |

## Telemetry and Reporting

| Term | Definition | Source |
|---|---|---|
| **OTel Span** | OpenTelemetry span emitted during evaluation. | §4.5 |
| **Listener** | Robot Framework hook (`OTelListener`) embedding spans + metrics into `log.html`. | §4.5 |
| **Report Artifact** | Final HTML/JSON output combining scorecards, baselines, and statistical comparisons. | §4.5 |
| **Baseline** | A stored prior run used as comparison reference. | §3.4, §4.5 |
| **Canary Suite** | Nightly re-run of fixed prompts vs. baseline to flag vendor-side regressions. | §8.6 |
