*** Settings ***
Documentation    ADR-021 acceptance — load an rf-mcp v1 scenario YAML
...              (byte-equivalent to manykarim/rf-mcp/tests/e2e/scenarios/*),
...              run it manually, save the JSON artifact in rf-mcp metrics
...              shape. Drop-in compatibility proof.
Library          AgentGuard
Library          OperatingSystem
Suite Setup      Connect Echo

*** Variables ***
${SCENARIO_YAML}    ${CURDIR}/../../fixtures/mcp_scenarios/echo_smoke.yaml

*** Test Cases ***
Load Scenario YAML In Rf Mcp Format
    [Tags]    mcp-scenario    yaml    drop-in
    ${scenario}=    Load MCP Scenario    ${SCENARIO_YAML}
    Should Be Equal As Strings    ${scenario.id}    echo_smoke
    Should Be Equal As Strings    ${scenario.context}    api
    ${tool}=    Set Variable    ${scenario.expected_tools}[0]
    Should Be Equal As Strings    ${tool.tool_name}    add

Run Yaml Scenario And Persist Result
    [Tags]    mcp-scenario    yaml    persistence
    ${scenario}=    Load MCP Scenario    ${SCENARIO_YAML}
    ${session}=    Start Tracked MCP Session    ${HANDLE}
    Call Tracked Tool    ${session}    add    {"x": 2, "y": 3}
    Call Tracked Tool    ${session}    echo    {"text": "yaml-driven"}
    End Tracked MCP Session    ${session}

    ${result}=    Compute Scenario Result    ${scenario}    ${session}
    Tool Hit Rate Should Be Above    ${result}    ${scenario.min_tool_hit_rate}
    ${path}=    Save Scenario Result    ${result}    ${OUTPUT_DIR}/echo_smoke.json
    ${exists}=    Evaluate    __import__('os').path.exists(r"${path}")
    Should Be True    ${exists}

*** Keywords ***
Connect Echo
    ${server}=    Evaluate    __import__('tests.fixtures.mcp.echo_server', fromlist=['mcp']).mcp
    ${handle}=    Connect To MCP Server    ${server}    transport=memory
    Set Suite Variable    ${HANDLE}    ${handle}
