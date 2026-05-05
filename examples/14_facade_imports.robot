*** Settings ***
Documentation    Phase-4-D example — sub-library façade imports per
...              ``docs/proposals/PROPOSAL-library-import-structure.md`` §3.
...
...              Demonstrates the four most-used façades side-by-side:
...              ``AgentGuard.MCP``, ``AgentGuard.Skill``, ``AgentGuard.Stats``
...              and ``AgentGuard.Scenario``. Each façade exposes its own
...              keyword set with no Python-path noise (no ``WITH NAME``
...              ceremony, no ``AgentGuard.mcp.library`` deep paths).
...
...              Runs offline via the in-memory FastMCP echo server fixture:
...                  PYTHONPATH=. uv run robot --include smoke
...                  ...               examples/14_facade_imports.robot
Library          AgentGuard.MCP
Library          AgentGuard.Skill
Library          AgentGuard.Stats
Library          AgentGuard.Scenario
Suite Setup      Connect Echo
Suite Teardown   Stop MCP Server    ${HANDLE}

*** Variables ***
${SKILL_PATH}    ${CURDIR}/../tests/fixtures/skills/good-skill

*** Test Cases ***
MCP Façade Reaches Its Own Keywords Without Prefix
    [Documentation]    `Library AgentGuard.MCP` exposes MCPKeywords aliased
    ...                as `MCP` — keywords are reachable directly.
    [Tags]    facade    mcp    smoke
    ${tools}=    List MCP Tools    ${HANDLE}
    ${names}=    Evaluate    [t['name'] for t in $tools]
    Should Contain    ${names}    add
    Should Contain    ${names}    echo

Skill Façade Reaches Its Own Keywords Without Prefix
    [Documentation]    `Library AgentGuard.Skill` exposes SkillsKeywords
    ...                aliased as `Skill`.
    [Tags]    facade    skill    smoke
    ${skill}=    Load Skill    ${SKILL_PATH}
    Validate Skill Frontmatter    ${skill}
    Should Be Equal As Strings    ${skill.name}    good-example

Stats Façade Reaches Its Own Keywords Without Prefix
    [Documentation]    `Library AgentGuard.Stats` exposes StatsKeywords
    ...                aliased as `Stats`. Synthetic samples — no live LLM.
    [Tags]    facade    stats    smoke
    ${current}=     Evaluate    [0.91, 0.93, 0.94, 0.95, 0.92, 0.96, 0.94, 0.93, 0.95, 0.94]
    ${baseline}=    Evaluate    [0.78, 0.80, 0.79, 0.82, 0.81, 0.79, 0.80, 0.81, 0.78, 0.79]
    Mann Whitney U Should Show Improvement    ${current}    ${baseline}    alpha=0.05

Scenario Façade Reaches Its Own Keywords Without Prefix
    [Documentation]    `Library AgentGuard.Scenario` exposes
    ...                MCPScenarioKeywords aliased as `Scenario`.
    [Tags]    facade    scenario    smoke
    ${scenario}=    Create Scenario    id=facade_demo    prompt=Use add(2,3)
    ...    expected_outcome=add returns 5    context=api    min_tool_hit_rate=0.99
    Add Expected Tool    ${scenario}    add    min_calls=1    max_calls=2

    ${session}=    Start Tracked MCP Session    ${HANDLE}
    Call Tracked Tool    ${session}    add    {"x": 2, "y": 3}
    End Tracked MCP Session    ${session}

    ${result}=    Compute Scenario Result    ${scenario}    ${session}
    Tool Hit Rate    ${result}    >=    ${0.99}

*** Keywords ***
Connect Echo
    ${server}=    Evaluate    __import__('tests.fixtures.mcp.echo_server', fromlist=['mcp']).mcp
    ${handle}=    Connect To MCP Server    ${server}    transport=memory
    Set Suite Variable    ${HANDLE}    ${handle}
