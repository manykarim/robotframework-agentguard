*** Settings ***
Documentation    Acceptance — research §6.4: Get Agent Card from in-process A2A server.
Library          AgentGuard    provider=mock
Library          ${CURDIR}/inproc_helper.py
Suite Setup      Setup Travel Planner Agents
Suite Teardown   Teardown Inproc Agents

*** Test Cases ***
Get Agent Card Returns Skills
    [Tags]    a2a    subagent    discovery    phase2
    ${card}=    Get Agent Card    inproc://travel_planner
    Should Be Equal As Strings    ${card.name}    travel_planner
    @{skills}=    List Agent Skills    ${card}
    Length Should Be    ${skills}    1

Validate Agent Card Accepts Dict
    [Tags]    a2a    subagent    validate    phase2
    ${raw}=    Create Dictionary    name=demo    version=1.0    url=inproc://demo
    ${card}=    Validate Agent Card    ${raw}
    Should Be Equal As Strings    ${card.name}    demo
