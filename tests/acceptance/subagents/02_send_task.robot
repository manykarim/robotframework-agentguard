*** Settings ***
Documentation    Acceptance — research §6.4: Send Task + wait + status assertion.
Library          AgentGuard    provider=mock
Library          ${CURDIR}/inproc_helper.py
Suite Setup      Setup Travel Planner Agents
Suite Teardown   Teardown Inproc Agents

*** Test Cases ***
Send Task Returns Completed
    [Tags]    a2a    subagent    lifecycle    phase2
    ${task}=    Send Task    inproc://travel_planner    Plan a 3-day trip to Lisbon
    Task Should Have Status    ${task}    completed

Get Task Artifact Text Has Trip Summary
    [Tags]    a2a    subagent    artifacts    phase2
    ${task}=    Send Task    inproc://travel_planner    Plan a 2-day trip to Porto
    ${text}=    Get Task Artifact Text    ${task}
    Should Contain    ${text}    Plan
