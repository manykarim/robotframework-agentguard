*** Settings ***
Documentation    Phase-1 example mirroring research §6.1 — MCP server basics.
...              Uses the in-memory FastMCP echo server fixture so it runs offline
...              with no subprocess/network dependencies (~2 ms/call per exp_01).
Library          AgentGuard
Suite Setup      Connect To Echo Server
Suite Teardown   Stop MCP Server    ${HANDLE}

*** Test Cases ***
List Tools On The MCP Server
    [Tags]    mcp    smoke
    ${tools}=    List MCP Tools    ${HANDLE}
    ${names}=    Evaluate    [t['name'] for t in $tools]
    Should Contain    ${names}    add
    Should Contain    ${names}    echo
    Should Contain    ${names}    slow_op

Add Tool Returns Correct Sum
    [Tags]    mcp    smoke
    ${result}=    Call MCP Tool    ${HANDLE}    add    {"x": 5, "y": 3}
    Should Be Equal As Integers    ${result}[data]    8

Echo Tool Round-Trips Payload
    [Tags]    mcp    smoke
    ${result}=    Call MCP Tool    ${HANDLE}    echo    {"text": "hello"}
    Should Be Equal As Strings    ${result}[data]    hello

In-Memory Latency Within Budget
    [Tags]    mcp    perf
    ${stats}=    Measure MCP Tool Latency    ${HANDLE}    add    runs=20    arguments={"x": 1, "y": 2}
    Should Be True    ${stats}[p50] < 50

*** Keywords ***
Connect To Echo Server
    ${server}=    Evaluate    __import__('tests.fixtures.mcp.echo_server', fromlist=['mcp']).mcp
    ${handle}=    Connect To MCP Server    ${server}    transport=memory
    Set Suite Variable    ${HANDLE}    ${handle}
