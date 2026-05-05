*** Settings ***
Documentation    Phase-2 example mirroring research §6.4 — A2A delegation lifecycle.
...
...              Uses the in-process travel_planner fixture (composite agent
...              that delegates to weather + places sub-agents). Runs offline
...              and asserts:
...
...                * AgentCard advertises ``trip.plan`` with the right tags.
...                * Send Task / Wait For Task Completion lifecycle works.
...                * Task transitions to ``completed`` status.
...                * Delegation trajectory matches the BFCL-shaped expected
...                  sequence (``delegate -> delegate -> compose``) via the
...                  Phase-1 BFCL trajectory matcher.
...                * Itinerary artifact's metadata captures the full
...                  ``delegation_chain`` (parent + child task IDs).
...
...              The fixture is registered against the in-process A2A server
...              shipped by the SubAgents module; no httpx, no network.
...              Live tests against a real A2A endpoint use the same
...              keyword surface and tag ``live``.
Library          AgentGuard
Library          Collections
Library          OperatingSystem
Suite Setup      Start Travel Planner Fixture
Suite Teardown   Stop Travel Planner Fixture

*** Test Cases ***
Travel Planner Card Advertises Trip Skill
    [Tags]    a2a    subagent    phase2
    Skip If    not ${PLANNER_AVAILABLE}    SubAgents module not yet wired
    ${card}=    Get Agent Card    ${PLANNER_URL}
    ${skill_ids}=    Evaluate    [s.id for s in $card.skills]
    Should Contain    ${skill_ids}    trip.plan

Travel Planner Delegates To Weather And Places
    [Documentation]    research §6.4 — Send Task + Task Trajectory Should Match.
    [Tags]    a2a    subagent    trajectory    phase2
    Skip If    not ${PLANNER_AVAILABLE}    SubAgents module not yet wired
    ${task}=    Send Task    ${PLANNER_URL}    Plan a trip to Lisbon
    ${task}=    Wait For Task Completion    ${task}    timeout=10
    Get Task Status    ${task}    ==    completed
    ${task}=    Attach Synthetic Tool Calls    ${task}
    @{expected}=    Create List    delegate    delegate    compose
    Task Trajectory Should Match    ${task}    ${expected}

Itinerary Artifact Records Delegation Chain
    [Tags]    a2a    subagent    artifact    phase2
    Skip If    not ${PLANNER_AVAILABLE}    SubAgents module not yet wired
    ${task}=    Send Task    ${PLANNER_URL}    Plan a trip to Tokyo
    ${task}=    Wait For Task Completion    ${task}    timeout=10
    ${artifacts}=    Get Task Artifact    ${task}
    ${chain}=    Extract Delegation Chain From Artifact    ${artifacts}[0]
    Should Be True    len($chain.links) == 2
    ${agents}=    Evaluate    sorted([l.agent_name for l in $chain.links])
    Should Be Equal As Strings    ${agents}    ['places-agent', 'weather-agent']

*** Keywords ***
Start Travel Planner Fixture
    [Documentation]    Bring up the planner + child agents in-process. Sets
    ...    ${PLANNER_AVAILABLE}=False and skips when SubAgents is not yet
    ...    wired so the example degrades cleanly mid-Phase-2.
    Set Suite Variable    ${PLANNER_AVAILABLE}    ${False}
    Set Suite Variable    ${PLANNER_URL}    ${EMPTY}
    ${ok}=    Run Keyword And Return Status    Try Start Travel Planner
    Set Suite Variable    ${PLANNER_AVAILABLE}    ${ok}

Try Start Travel Planner
    ${factory}=    Evaluate    __import__('tests.fixtures.a2a.travel_planner', fromlist=['make_travel_planner']).make_travel_planner
    ${result}=    Call Function    ${factory}
    ${planner}=    Set Variable    ${result}[0]
    Set Suite Variable    ${PLANNER}    ${planner}
    Set Suite Variable    ${PLANNER_URL}    ${planner.url}

Stop Travel Planner Fixture
    Run Keyword And Ignore Error    Call Method    ${PLANNER}    stop

Call Function
    [Arguments]    ${fn}    @{args}    &{kwargs}
    ${out}=    Evaluate    $fn(*$args, **$kwargs)
    RETURN    ${out}

Extract Delegation Chain From Artifact
    [Arguments]    ${artifact}
    ${extractor}=    Evaluate    __import__('tests.fixtures.a2a.travel_planner', fromlist=['extract_delegation_chain']).extract_delegation_chain
    ${chain}=    Call Function    ${extractor}    ${artifact}
    RETURN    ${chain}

Attach Synthetic Tool Calls
    [Documentation]    Copy `tool_calls` from the planner's artifact metadata
    ...    onto the last agent message so Task Trajectory Should Match can
    ...    walk the BFCL grammar (the in-process server doesn't auto-attach).
    [Arguments]    ${task}
    ${attach}=    Evaluate    __import__('tests.fixtures.a2a.travel_planner', fromlist=['attach_tool_calls_to_messages']).attach_tool_calls_to_messages
    ${task_mod}=    Evaluate    __import__('AgentGuard.subagents.types', fromlist=['Task']).Task
    ${rebuilt_messages}=    Call Function    ${attach}    ${task.messages}    ${task.artifacts}[0]
    ${rebuilt_task}=    Evaluate    __import__('dataclasses').replace($task, messages=tuple($rebuilt_messages))
    RETURN    ${rebuilt_task}
