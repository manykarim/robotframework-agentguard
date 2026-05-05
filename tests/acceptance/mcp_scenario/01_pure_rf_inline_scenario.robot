*** Settings ***
Documentation    ADR-021 acceptance — pure Robot Framework keyword-driven
...              scenario with no YAML. Demonstrates that every concept maps
...              to a clean RF keyword: Create Scenario, Add Expected Tool,
...              Start Tracked MCP Session, Call Tracked Tool, Compute
...              Scenario Result, Tool Hit Rate (operator form per ADR-022).
Library          AgentGuard
Suite Setup      Connect Echo
Suite Teardown   Stop MCP Server    ${HANDLE}

*** Test Cases ***
Inline Scenario Hits 100 Percent
    [Tags]    mcp-scenario    inline    smoke
    ${scenario}=    Create Scenario    id=echo_inline    prompt=add 2 3
    ...    expected_outcome=add returns 5    context=api    min_tool_hit_rate=0.99
    Add Expected Tool    ${scenario}    add    min_calls=1    max_calls=2
    Add Expected Tool    ${scenario}    echo    min_calls=1    max_calls=2

    ${session}=    Start Tracked MCP Session    ${HANDLE}
    Call Tracked Tool    ${session}    add    {"x": 2, "y": 3}
    Call Tracked Tool    ${session}    echo    {"text": "hello"}
    End Tracked MCP Session    ${session}

    ${result}=    Compute Scenario Result    ${scenario}    ${session}
    Scenario Result Should Be Successful    ${result}
    Tool Hit Rate    ${result}    >=    ${0.99}
    Failed Tool Call Count    ${result}    <=    ${0}
    # `between` decomposes into paired `>=` / `<=` checks per ADR-022; the
    # single-call `validate` form is gated by ADR-013 sandbox policy.
    Tool Call Count    ${result}    assertion_operator=>=    assertion_expected=${2}
    Tool Call Count    ${result}    assertion_operator=<=    assertion_expected=${4}
    Tool Call Count    ${result}    name=echo    assertion_operator===    assertion_expected=${1}

Required Params Assertion Catches Param Drift
    [Tags]    mcp-scenario    inline    required-params
    ${scenario}=    Create Scenario    id=echo_params    prompt=—    expected_outcome=—
    ${session}=    Start Tracked MCP Session    ${HANDLE}
    Call Tracked Tool    ${session}    echo    {"text": "policy-required-banner"}
    End Tracked MCP Session    ${session}

    Required Tool Should Have Been Called With Params
    ...    ${session}    echo    {"text": "policy-required-banner"}

    Run Keyword And Expect Error    *required_params*
    ...    Required Tool Should Have Been Called With Params
    ...    ${session}    echo    {"text": "different"}

Tool Call Statistics Surface Is Robot-Friendly
    [Tags]    mcp-scenario    statistics
    ${session}=    Start Tracked MCP Session    ${HANDLE}
    Call Tracked Tool    ${session}    add    {"x": 1, "y": 1}
    Call Tracked Tool    ${session}    add    {"x": 2, "y": 2}
    Call Tracked Tool    ${session}    echo    {"text": "ok"}
    End Tracked MCP Session    ${session}

    ${stats}=    Tool Call Statistics    ${session}
    Should Be Equal As Integers    ${stats.total_tool_calls}    3
    Should Be Equal As Integers    ${stats.failed_calls}    0
    Should Be Equal As Integers    ${stats.successful_calls}    3
    ${counts}=    Set Variable    ${stats.tool_call_counts}
    Should Be Equal As Integers    ${counts}[add]    2
    Should Be Equal As Integers    ${counts}[echo]    1

Save And Load Scenario Result Round Trip
    [Tags]    mcp-scenario    persistence
    ${scenario}=    Create Scenario    id=echo_persist    prompt=—    expected_outcome=—
    Add Expected Tool    ${scenario}    add    min_calls=1    max_calls=1
    ${session}=    Start Tracked MCP Session    ${HANDLE}
    Call Tracked Tool    ${session}    add    {"x": 1, "y": 1}
    End Tracked MCP Session    ${session}
    ${result}=    Compute Scenario Result    ${scenario}    ${session}
    ${path}=    Save Scenario Result    ${result}    ${OUTPUT_DIR}/echo_persist.json
    ${exists}=    Evaluate    __import__('os').path.exists(r"${path}")
    Should Be True    ${exists}
    ${loaded}=    Load Scenario Result    ${path}
    Should Be Equal As Strings    ${loaded.scenario_id}    echo_persist

*** Keywords ***
Connect Echo
    ${server}=    Evaluate    __import__('tests.fixtures.mcp.echo_server', fromlist=['mcp']).mcp
    ${handle}=    Connect To MCP Server    ${server}    transport=memory
    Set Suite Variable    ${HANDLE}    ${handle}
