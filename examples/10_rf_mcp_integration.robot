*** Settings ***
Documentation    Phase-3 example — drive the rf-mcp Robot Framework MCP server
...              (https://github.com/manykarim/rf-mcp) end-to-end via AgentGuard's
...              MCP module. Uses the in-memory FastMCP transport so the suite
...              runs offline once `rf-mcp` is installed.
...
...              Install: uv add 'robotframework-agentguard[integrations]'
...                       OR pip install rf-mcp
Library          AgentGuard
Suite Setup      Connect To Rf Mcp Server
Suite Teardown   Stop MCP Server    ${HANDLE}

*** Test Cases ***
Rf Mcp Lists Documented Tools
    [Tags]    rf-mcp    smoke
    ${tools}=    List MCP Tools    ${HANDLE}
    ${names}=    Evaluate    [t['name'] for t in $tools]
    Should Contain    ${names}    analyze_scenario
    Should Contain    ${names}    find_keywords
    Should Contain    ${names}    manage_session

Rf Mcp Tool Count Within Expected Range
    [Tags]    rf-mcp
    ${tools}=    List MCP Tools    ${HANDLE}
    ${count}=    Get Length    ${tools}
    Should Be True    ${count} >= 10    rf-mcp 0.30+ ships at least 10 tools

Rf Mcp Find Keywords Returns A Result
    [Tags]    rf-mcp    smoke
    ${result}=    Call MCP Tool    ${HANDLE}    find_keywords    {"query": "log"}
    Should Be Equal    ${result}[is_error]    ${False}

Rf Mcp Capabilities Include Tools
    [Tags]    rf-mcp
    ${caps}=    Get MCP Capabilities    ${HANDLE}
    ${has_tools}=    Evaluate    "tools" in $caps
    Should Be True    ${has_tools}    msg=capabilities missing 'tools' key: ${caps}

Rf Mcp In-Memory Latency Within Budget
    [Tags]    rf-mcp    perf
    ${stats}=    Measure MCP Tool Latency    ${HANDLE}    find_keywords    runs=10
    ...    arguments={"query": "x"}
    Should Be True    ${stats}[p50] < 250    p50=${stats}[p50]ms

*** Keywords ***
Connect To Rf Mcp Server
    [Documentation]    Import rf-mcp's module-level FastMCP instance and bind
    ...                AgentGuard's MCP client over the in-memory transport.
    ...                Falls back to a local clone under ~/workspace/rf-mcp/src
    ...                so contributors don't need to pip-install during dev.
    ${available}=    Ensure Robotmcp Importable
    Skip If    not ${available}
    ...    rf-mcp not installed; uv add 'robotframework-agentguard[integrations]' (or pip install rf-mcp)
    ${server}=    Evaluate    __import__('robotmcp.server', fromlist=['mcp']).mcp
    ${handle}=    Connect To MCP Server    ${server}    transport=memory
    Set Suite Variable    ${HANDLE}    ${handle}

Ensure Robotmcp Importable
    ${clone}=    Evaluate    str(__import__('pathlib').Path.home() / 'workspace' / 'rf-mcp' / 'src')
    Evaluate    sys.path.insert(0, r"${clone}") if r"${clone}" not in sys.path else None    modules=sys
    ${spec}=    Evaluate    __import__('importlib').util.find_spec('robotmcp')
    ${ok}=    Evaluate    $spec is not None
    RETURN    ${ok}
