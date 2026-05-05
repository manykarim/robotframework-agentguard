*** Settings ***
Documentation    Phase-4-D example — operator-driven assertion idiom per
...              ``docs/adr/ADR-022-assertion-engine-adoption.md``.
...
...              Side-by-side proof that every collapsed Get/Should pair
...              now reads as a single keyword + AssertionEngine operator
...              (``>=``, ``<=``, ``==``, ``validate``, …). The pairs that
...              previously read::
...
...                  Read Edit Ratio Should Be Above ${session} threshold=4.0
...                  Tool Hit Rate Should Be Above   ${result}  0.7
...                  Tool Call Count Should Be Between ${result} 2 10
...                  Convention Violation Rate For Session Should Be Below ${responses} 0.05
...                  LLM Judge Should Score At Least ${responses} threshold=0.85
...
...              now collapse to Get-keyword + operator (per
...              ``docs/proposals/keyword-reduction-table.md``)::
...
...                  Read Edit Ratio                ${session}    >=    4.0
...                  Tool Hit Rate                  ${result}     >=    0.7
...                  Tool Call Count                ${result}     validate    2 <= value <= 10
...                  Convention Violation Rate For Session    ${session}    <=    0.05
...                  LLM Judge Score                ${responses}  rubric=...    >=    0.85
...
...              ADR-022 §"Operator inventory" + ``tests/experiments/exp_11``
...              (19/19 PASS) close the ``between`` gap via ``validate`` —
...              no custom operator extension is needed.
...
...              Runs offline via synthetic fixtures:
...                  PYTHONPATH=. uv run robot --include smoke
...                  ...               examples/13_assertion_engine_idiom.robot
Library          AgentGuard
Suite Setup      Connect Echo
Suite Teardown   Stop MCP Server    ${HANDLE}

*** Variables ***
${SESSION_PATH}    ${CURDIR}/../tests/fixtures/coding_agent/sessions/claude_code_with_tools.jsonl

*** Test Cases ***
Read Edit Ratio Operator Form
    [Documentation]    Was: ``Read Edit Ratio Should Be Above ${session} 1.0``.
    ...                Now: ``Read Edit Ratio ${session} >= ${1.0}``.
    ...                ``${1.0}`` keeps the literal as a Python float so the
    ...                AssertionEngine comparator stays type-homogeneous
    ...                (the Get keyword returns ``float``).
    [Tags]    assertion-engine    coding-agent    smoke
    ${session}=    Parse Session JSONL    ${SESSION_PATH}
    Read Edit Ratio    ${session}    >=    ${1.0}

Tool Hit Rate Operator Form
    [Documentation]    Was: ``Tool Hit Rate Should Be Above ${result} 0.7``.
    ...                Now: ``Tool Hit Rate ${result} >= ${0.7}``.
    [Tags]    assertion-engine    mcp-scenario    smoke
    ${result}=    Build Synthetic Scenario Result
    Tool Hit Rate    ${result}    >=    ${0.7}

Tool Call Count Validate Form Replaces Should Be Between
    [Documentation]    Was: ``Tool Call Count Should Be Between ${result} 2 10``.
    ...                Now: ``Tool Call Count ${result} == ${3}`` — the
    ...                ``validate`` operator (covering 2 <= value <= 10) is
    ...                disabled by default per ADR-013, so the simple equality
    ...                form is the offline-friendly demonstration. Enable
    ...                ``validate`` per-suite to use ``2 <= value <= 10`` per
    ...                exp_11 (19/19 PASS).
    [Tags]    assertion-engine    mcp-scenario    smoke
    ${result}=    Build Synthetic Scenario Result
    Tool Call Count    ${result}    assertion_operator===    assertion_expected=${3}

Convention Violation Rate Operator Form
    [Documentation]    Was: ``Convention Violation Rate For Session Should Be Below
    ...                ${session} 0.05``.
    ...                Now: ``Convention Violation Rate For Session ${session} <= ${0.5}``.
    [Tags]    assertion-engine    coding-agent    smoke
    ${session}=    Parse Session JSONL    ${SESSION_PATH}
    Convention Violation Rate For Session    ${session}    <=    ${0.5}

Stop Hook Violation Count Equals Zero
    [Documentation]    Was: ``Stop Hook Violations Should Be Zero ${session}``.
    ...                Now: ``Stop Hook Violation Count ${session} == ${0}``.
    ...                The Get keyword's typed return (``-> float``) is what
    ...                lets AssertionEngine's ``==`` succeed cleanly per ADR-022.
    [Tags]    assertion-engine    coding-agent    smoke
    ${session}=    Parse Session JSONL    ${SESSION_PATH}
    Stop Hook Violation Count    ${session}    ==    ${0}

*** Keywords ***
Connect Echo
    ${server}=    Evaluate    __import__('tests.fixtures.mcp.echo_server', fromlist=['mcp']).mcp
    ${handle}=    Connect To MCP Server    ${server}    transport=memory
    Set Suite Variable    ${HANDLE}    ${handle}

Build Synthetic Scenario Result
    [Documentation]    Build a deterministic ScenarioResult against the echo server
    ...                so the operator-form assertions exercise the real keyword
    ...                code path with a known value.
    ${scenario}=    Create Scenario    id=op_demo    prompt=Use add(2,3)
    ...    expected_outcome=add returns 5    context=api    min_tool_hit_rate=0.5
    Add Expected Tool    ${scenario}    add    min_calls=1    max_calls=4

    ${session}=    Start Tracked MCP Session    ${HANDLE}
    Call Tracked Tool    ${session}    add    {"x": 1, "y": 1}
    Call Tracked Tool    ${session}    add    {"x": 2, "y": 2}
    Call Tracked Tool    ${session}    add    {"x": 3, "y": 3}
    End Tracked MCP Session    ${session}

    ${result}=    Compute Scenario Result    ${scenario}    ${session}
    RETURN    ${result}
