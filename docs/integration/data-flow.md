# End-to-end Data Flow — One Skill Grading Run

This document traces a single Robot Framework `.robot` test for one Agent Skill from user invocation through final report, showing exactly which RuFlo capability fires at each step. Reference for `adr-architect` ADRs ADR-015 (baselines), ADR-017 (judge), ADR-018 (behavioral metrics), ADR-020 (SONA + AIDefence).

## Sequence diagram

```mermaid
sequenceDiagram
    autonumber
    actor QA as QA Engineer
    participant RF as Robot Framework Runner
    participant AT as AgentTest Library<br/>(Skills context)
    participant H as RuFlo Hooks Router<br/>(hooks_route)
    participant M as RuFlo AgentDB<br/>(memory_*)
    participant AD as RuFlo AIDefence<br/>(aidefence_*)
    participant SK as SKILL.md on disk
    participant CC as CodingAgentDriver<br/>(claude-code subprocess)
    participant W as WASM Tier-1 calculators<br/>(11 #42796 metrics)
    participant J as Judge (Tier-2 / Tier-3)<br/>(hooks_model-route)
    participant S as RuFlo SONA<br/>(hooks_intelligence_*)
    participant T as Telemetry / OTel listener
    participant OUT as output.xml + log.html

    QA->>RF: robot tests/skills/browser_skill.robot
    RF->>AT: Suite Setup → Load Skill "browser-skill"
    AT->>H: hooks_session-start (suite_id, skill_id)
    H->>M: memory_search ns=agentguard/baselines/skills<br/>query="browser-skill::sonnet-4.5::gpt-4o"
    M-->>AT: prior baseline scorecard (or null)
    AT->>H: hooks_pre-task (event=Load Skill)
    H->>AD: aidefence_scan (SKILL.md content)
    AD-->>H: {is_safe: true, pii: false, injection_score: 0.02}
    AD->>M: memory_store ns=agentguard/security/scans (audit trail)
    AT->>SK: parse frontmatter (name, description, allowed-tools)
    AT->>M: memory_search ns=agentguard/patterns/failures<br/>query=embedded(skill description)
    M-->>AT: top-5 prior similar failures (SONA-distilled)
    AT->>S: hooks_intelligence_trajectory-start (run_id)

    Note over AT,CC: Test body — Run Skill Eval N=10 times
    loop N=10 runs (research §2.7 non-determinism)
        AT->>CC: Run Coding Agent driver=claude-code prompt=<eval prompt>
        CC->>CC: spawn `claude` CLI subprocess in sandbox
        CC-->>AT: JSONL session log path
        AT->>S: hooks_intelligence_trajectory-step (tool_calls, thinking)
        AT->>AD: aidefence_has_pii (transcript)
        AD-->>AT: PII-scrubbed transcript
        AT->>W: Tier-1 WASM — compute 11 #42796 metrics<br/>(Read:Edit, EditsWithoutRead, ReasoningLoops, ...)
        W-->>AT: metric vector (sub-ms, $0)
        AT->>H: hooks_model-route (complexity=judge_call)
        alt complexity < 30%
            H-->>J: route → Tier-2 (Haiku)
        else complexity ≥ 30%
            H-->>J: route → Tier-3 (Sonnet/Opus)
        end
        AT->>J: LLM Judge Should Score At Least<br/>(rubric, transcript, expected_output)
        J-->>AT: {score, rationale, judge_id}
        AT->>M: memory_store ns=agentguard/runs<br/>(metric vector + judge verdict)
    end

    Note over AT,M: Statistical assertions over the N=10 results
    AT->>M: memory_search ns=agentguard/baselines/behavioral<br/>(nearest-neighbour cohort)
    M-->>AT: baseline cohort (k=20 nearest by skill+model)
    AT->>AT: scipy Mann-Whitney U + Cliff's delta vs baseline
    AT->>AT: Pass@k, TARr@N (research §3.4)

    alt judges disagreed by >0.15σ
        AT->>H: hive-mind_consensus mode=byzantine N=5
        H-->>AT: consensus verdict
    end

    AT->>M: memory_store ns=agentguard/baselines/skills<br/>(new baseline scorecard, ewc=true)
    AT->>S: hooks_intelligence_trajectory-end (run_id, verdict)
    S->>S: hooks_intelligence_pattern-store<br/>(if recurring failure → distill template)
    AT->>H: hooks_post-task (event=Skill Eval Complete)
    H->>S: hooks_intelligence_learn (mode=ewc, new baseline)
    H->>T: emit OTel spans (compatible with mcp-eval)
    AT->>H: hooks_session-end
    H->>M: memory consolidation (worker `consolidate` queued)
    T-->>RF: spans → Robot listener
    RF->>OUT: output.xml + log.html with embedded scorecard,<br/>baseline diff, judge rationales, OTel traces
    OUT-->>QA: Pass/Fail + report
```

## Step annotations

| Step range | DDD context | RuFlo capability | Notes |
|---|---|---|---|
| 1–4 | Skills + Hooks | `hooks_session-start`, `memory_search` | Baseline pre-fetch ADR-015 |
| 5–8 | Security + Skills | `aidefence_scan`, `memory_store` audit | Mandatory (research §8.3) |
| 9–11 | BehavioralMetrics + SONA | `memory_search` failure patterns, `trajectory-start` | Surfaces "similar past failures" panel |
| 12–22 | CodingAgent + Telemetry | `trajectory-step`, `aidefence_has_pii`, WASM Tier-1, `hooks_model-route` | Inner loop, N=10 (research §2.7) |
| 23–26 | Statistics | `memory_search` baseline cohort, scipy stats | ADR-018 |
| 27–29 | Judge | `hive-mind_consensus` (Byzantine) | Only fires on judge disagreement; ADR-017 |
| 30–34 | Skills + SONA + Telemetry | `memory_store` (EWC), `pattern-store`, `hooks_intelligence_learn`, `hooks_post-task` | Persists learning |
| 35–38 | Telemetry | OTel listener, output.xml | Standard Robot reporting + embedded RuFlo metrics |

## Key invariants

- **Every external input is AIDefence-scanned** before reaching the judge or being persisted.
- **Tier-1 WASM runs first** for the 11 deterministic metrics; LLM judges only fire when the metric vector or rubric demands it (cost discipline).
- **Baselines are stored with EWC++** so adding a new skill never overwrites prior skill baselines.
- **Judge disagreements escalate to Byzantine consensus**, not silently averaged.
- **Trajectories are SONA-recorded for every run**, not only failures, so pattern extraction has positive examples too.
