# Anti-Drift Strategy — robotframework-agentguard

How AgentGuard uses RuFlo's anti-drift features to keep its **own** test runs deterministic across sessions, machines, and CI shards.

Cite: `CLAUDE.md` → "Swarm Configuration & Anti-Drift" + "Swarm Execution Rules".

## The problem

Research §2.7 establishes that `temperature=0` does not yield reproducibility (15% variance, 70% best-vs-worst). When AgentGuard tests itself (its own meta-suite, the per-skill canary, the auto-generation of test cases), the same instability applies — the *grader* drifts. RuFlo provides four primitives that, combined, bring drift below the noise floor required for AgentGuard's `Mann Whitney U Should Show Improvement` assertions to be trustworthy.

## The four primitives

### 1. Hierarchical topology (CLAUDE.md "Swarm Configuration")

> "ALWAYS use hierarchical topology for coding swarms — Keep maxAgents at 6-8 for tight coordination."

AgentGuard config (`CLAUDE.md` "Project Config"): **hierarchical-mesh, max 15 agents**. The hierarchical lead is the authoritative sequencer of test-generation steps. Mesh peers are the per-metric critics — they consume the lead's outputs but cannot reorder them. This eliminates the most common drift source: agents racing to commit baselines in different orders on different machines.

| Drift source | How hierarchical fixes it |
|---|---|
| Two CI shards generate baselines for the same skill in different order | Lead serialises baseline writes; mesh critics produce read-only votes |
| Long coding-agent runs tail-off into rambling | Lead enforces step budget; on overshoot, hierarchical kill (CLAUDE.md "Swarm Execution Rules") |
| New agent type added → topology auto-rebalances unpredictably | Hierarchical lead is the only authority that admits new peers |

CLI: `npx @claude-flow/cli@latest swarm init --topology hierarchical --max-agents 8 --strategy specialized`

### 2. Raft consensus for hive-mind (CLAUDE.md "Swarm Configuration")

> "Use `raft` consensus for hive-mind (leader maintains authoritative state)."

AgentGuard uses raft (not Byzantine) for **routine baseline writes** because raft has a single source of truth — the elected leader. Byzantine PBFT is reserved for the *judge disagreement escalation path* (see `data-flow.md` step 27-29) where we explicitly want N=5 independent verdicts.

The split:

| Operation | Consensus | Why |
|---|---|---|
| Write a new skill baseline | raft | Single authoritative state, no forks across CI shards |
| Vote "is this auto-generated test deterministic enough to commit" | raft | Leader = the agent that ran the N=20 trial; quorum = simple majority |
| Resolve judge disagreement (>0.15σ) | Byzantine PBFT | Independence is the point; no single leader should bias the vote |
| Distill SONA patterns | raft via the `consolidate` worker | One nightly consolidation, leader = the worker |

### 3. Frequent post-task checkpoints (CLAUDE.md "Anti-Drift")

> "Run frequent checkpoints via `post-task` hooks."

AgentGuard registers a `hooks_post-task` handler that, after every Robot Framework keyword that mutates state (`Run Skill Eval`, `Run Coding Agent`, `Calibrate Judge`, `Run Hook Command`), emits a checkpoint into AgentDB at namespace `agentguard/checkpoints/<suite_id>/<test_id>/<timestamp>`. The checkpoint contains:

- skill / hook / agent under test (id + content hash);
- model + judge (id + version);
- input prompt (or hash if PII-scrubbed);
- output metric vector (the 11 #42796 numbers + judge score);
- random seeds + provider headers.

If a re-run produces a different metric vector for the same content+model+judge tuple, the listener flags it as drift, not failure, and the `benchmark` worker investigates.

This is the single most important anti-drift mechanism: it makes drift **observable** rather than something that silently shifts thresholds.

### 4. Shared memory namespace for all agents (CLAUDE.md "Swarm Configuration")

> "Keep shared memory namespace for all agents."

Every AgentGuard agent (test generator, per-metric critic, judge, aggregator) reads/writes to the **same** AgentDB namespace tree under `agentguard/<suite_id>/`. No agent has a private working memory. Consequences:

- A new agent cannot accidentally fork the baseline.
- Two CI shards see identical context.
- The `consolidate` worker has a single tree to walk nightly.

Namespace layout enforced by AgentGuard:

```
agentguard/
  baselines/skills/<skill_id>::<model>::<judge>
  baselines/behavioral/<session_hash>
  datasets/bfcl/<category>
  judge/calibration/<judge_id>
  patterns/failures/<pattern_id>
  checkpoints/<suite_id>/<test_id>/<ts>
  security/scans/<content_hash>
  runs/<run_id>
```

## Operating rules (enforced)

These are derived from CLAUDE.md "Swarm Execution Rules" + "Concurrency: 1 MESSAGE = ALL RELATED OPERATIONS":

1. **All Agent tool spawns happen in one message, with `run_in_background: true`** — prevents partial swarm states.
2. **Never poll agent status** — wait for results; the post-task checkpoint is the only valid completion signal.
3. **Listener `start_suite` validates** that the topology, consensus mode, and namespace match the project config before any test runs.
4. **Drift alarm**: `benchmark` worker re-runs the canary suite hourly; if `Mann Whitney U Should Show Improvement` fails against the prior 24h baseline, the worker pages QA via `hooks_notify`.

## What this buys AgentGuard

| Without anti-drift | With the four primitives |
|---|---|
| Same skill grades 0.78 / 0.84 / 0.71 on three CI shards | Same skill grades within ±0.02 across shards |
| Judge slowly migrates as model versions update | Calibration set + raft baseline catches drift within one canary cycle |
| Auto-generated test commits a flaky suite | Hive-mind raft vote (TARr@20 ≥ 0.85) blocks the commit |
| Lost track of which baseline a regression test compared against | Every checkpoint is content-addressed, traceable, and reproducible |

## Summary

The four CLAUDE.md anti-drift rules — hierarchical topology, raft consensus, frequent post-task checkpoints, shared memory namespace — together turn AgentGuard's own test runs from "non-deterministic but loud" into "non-deterministic but observable". That is exactly the property research §2.7 says is achievable and §8.6 says is required. ADR-019 documents the swarm architecture; this file documents the determinism contract.
