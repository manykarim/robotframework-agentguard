*** Settings ***
Documentation    Phase-3 example mirroring research §6.5 — #42796 behavioural metric pack.
...              Updated for Phase-4-D (ADR-022): every metric assertion uses the
...              operator form (``>=``, ``<=``, ``==``) instead of the deleted
...              ``Should Be Above|Below|Zero`` keywords.
...
...              Parses a synthetic Claude Code session JSONL (committed under
...              ``tests/fixtures/coding_agent/sessions/``) and asserts each of
...              the canonical #42796 metrics against deliberately loose
...              thresholds. The synthetic fixture is small (a dozen records,
...              5 tool calls) so the point of this example is to demonstrate
...              the keyword wiring end-to-end — *not* to enforce production
...              thresholds. For real regression gating use ``Compute 42796
...              Metric Pack`` + ``Behavioral Report Should Match Baseline``
...              against a stored baseline, exactly as research §2.6 prescribes.
...
...              Runnable offline via:
...                  PYTHONPATH=. uv run robot examples/05_coding_agent_metrics.robot
Library          AgentGuard

*** Variables ***
${SESSION_PATH}=    ${CURDIR}/../tests/fixtures/coding_agent/sessions/claude_code_with_tools.jsonl

*** Test Cases ***
Claude Code Maintains Healthy Read-Edit Discipline
    [Documentation]    research §6.5 — wiring smoke for the #42796 metric pack
    ...                in the post-ADR-022 operator form.
    [Tags]    coding-agent    behavioral    phase3
    ${session}=    Parse Session JSONL    ${SESSION_PATH}
    Read Edit Ratio                          ${session}    >=    ${1.0}
    Edits Without Prior Read Percent         ${session}    <=    ${50}
    Reasoning Loops Per 1K Tool Calls        ${session}    <=    ${100}
    User Interrupts Per 1K Tool Calls        ${session}    <=    ${50}
    Stop Hook Violation Count                ${session}    ==    ${0}

Compute Full 42796 Metric Pack On Same Session
    [Documentation]    Aggregate keyword that returns a BehavioralReport with all
    ...                12 calculators populated. Useful when you want to log
    ...                the full pack without per-metric assertions.
    [Tags]    coding-agent    behavioral    phase3
    ${session}=    Parse Session JSONL    ${SESSION_PATH}
    ${report}=     Compute 42796 Metric Pack    ${session}
    ${health}=     Get Session Health    ${session}
    Should Be Equal As Strings    ${report.session_id}    synthetic-tools-001
    Should Contain    ${report.metrics}    read_edit_ratio
    Log    overall health: ${health}
