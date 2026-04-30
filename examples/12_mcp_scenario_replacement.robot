*** Settings ***
Documentation    Phase 4-A — drop-in replacement for `manykarim/rf-mcp`
...              `tests/e2e/` patterns, demonstrated three ways:
...
...              (1) Pure RF keywords, no YAML — for users who want every
...                  scenario step to be a clearly-named Robot keyword.
...              (2) YAML-driven, rf-mcp v1 schema — drop-in for existing
...                  rf-mcp scenario libraries.
...              (3) Live-LLM driver — gated by ${LIVE} tag and
...                  OPENROUTER_API_KEY (the rf-mcp `USE_REAL_LLM=true`
...                  pattern, ported to AgentGuard).
Library          AgentGuard
Suite Setup      Connect Echo
Suite Teardown   Stop MCP Server    ${HANDLE}

*** Variables ***
${SCENARIO_YAML}    ${CURDIR}/../tests/fixtures/mcp_scenarios/echo_smoke.yaml

*** Test Cases ***
Pure Robot Framework — Inline Scenario
    [Tags]    mcp-scenario    inline    smoke
    ${scenario}=    Create Scenario    id=inline_demo    prompt=Use add(2,3) then echo
    ...    expected_outcome=add returns 5    context=api    min_tool_hit_rate=0.99
    Add Expected Tool    ${scenario}    add    min_calls=1    max_calls=2
    Add Expected Tool    ${scenario}    echo    min_calls=1    max_calls=2

    ${session}=    Start Tracked MCP Session    ${HANDLE}
    Call Tracked Tool    ${session}    add    {"x": 2, "y": 3}
    Call Tracked Tool    ${session}    echo    {"text": "ok"}
    End Tracked MCP Session    ${session}

    ${result}=    Compute Scenario Result    ${scenario}    ${session}
    Scenario Result Should Be Successful    ${result}
    Tool Hit Rate Should Be Above    ${result}    0.99
    Failed Tool Call Count Should Be At Most    ${result}    0

YAML-Driven — Rf Mcp V1 Schema
    [Tags]    mcp-scenario    yaml    smoke
    ${scenario}=    Load MCP Scenario    ${SCENARIO_YAML}
    ${session}=    Start Tracked MCP Session    ${HANDLE}
    Call Tracked Tool    ${session}    add    {"x": 2, "y": 3}
    Call Tracked Tool    ${session}    echo    {"text": "yaml-driven"}
    End Tracked MCP Session    ${session}

    ${result}=    Compute Scenario Result    ${scenario}    ${session}
    Tool Hit Rate Should Be Above    ${result}    ${scenario.min_tool_hit_rate}
    Save Scenario Result    ${result}    ${OUTPUT_DIR}/echo_smoke.json

Live LocalDriver — Real OpenRouter Through Echo Server
    [Documentation]    Reproduces rf-mcp's autonomous-agent test pattern:
    ...                a real LLM picks tools from the live MCP server's schema
    ...                and AgentGuard auto-records every dispatch. Cost ≈ \$0.001.
    [Tags]    mcp-scenario    live
    ${scenario}=    Create Scenario    id=live_echo    context=api
    ...    prompt=Call the add tool with x=4 and y=7 to compute their sum.
    ...    expected_outcome=add returns 11
    ...    min_tool_hit_rate=0.5
    Add Expected Tool    ${scenario}    add    min_calls=1    max_calls=3

    ${result}=    Run MCP Scenario    ${scenario}    server=${HANDLE}
    ...    driver=local    model=openrouter/openai/gpt-4o-mini    max_turns=4
    Tool Call Count Should Be Between    ${result}    min_count=1    max_count=10

*** Keywords ***
Connect Echo
    ${server}=    Evaluate    __import__('tests.fixtures.mcp.echo_server', fromlist=['mcp']).mcp
    ${handle}=    Connect To MCP Server    ${server}    transport=memory
    Set Suite Variable    ${HANDLE}    ${handle}
