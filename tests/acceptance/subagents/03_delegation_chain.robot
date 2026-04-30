*** Settings ***
Documentation    Acceptance — research §6.4: delegation-chain trajectory match.
Library          AgentGuard    provider=mock
Library          ${CURDIR}/inproc_helper.py
Suite Setup      Setup Travel Planner Agents
Suite Teardown   Teardown Inproc Agents

*** Test Cases ***
Delegation Trajectory Matches Expected Tool Sequence
    [Tags]    a2a    subagent    delegation    trajectory    phase2
    ${task}=    Send Task    inproc://travel_planner    Plan a trip to Lisbon
    Task Should Have Status    ${task}    completed
    Inject Synthetic Trajectory    ${task}
    @{expected}=    Create List    weather.lookup    places.search
    Task Trajectory Should Match    ${task}    ${expected}
