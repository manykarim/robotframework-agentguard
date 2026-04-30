*** Settings ***
Documentation    Phase-1 example mirroring research §6.6 — BFCL tool-selection.
...              Tier-1 only; runs offline against the 30-case golden fixture.
Library          AgentGuard
Library          OperatingSystem
Library          Collections

*** Variables ***
${GOLDEN}    ${CURDIR}/../tests/fixtures/tool_calls/golden_calls.json

*** Test Cases ***
Tool Call Matches Expected Name And Arguments
    [Tags]    bfcl    tool-call    offline
    ${actual}=    Create Dictionary    name=add    arguments={"x": 5, "y": 3}
    ${expected}=    Create Dictionary    name=add    arguments={"x": 5, "y": 3}
    Tool Call Should Match Name    ${actual}    add
    Tool Call Arguments Should Match    ${actual}    ${expected}[arguments]    mode=ast

Tool Sequence Matches With Wildcards
    [Tags]    bfcl    trajectory    offline
    ${seq}=    Evaluate    [{'name':'search'},{'name':'fetch'},{'name':'summarize'}]
    Tool Sequence Should Match    ${seq}    ['search', '*', 'summarize']

Decide Not To Call Any Tool
    [Tags]    bfcl    decide-not-to-act    offline
    ${empty}=    Create List
    Should Not Call Any Tool    ${empty}

Golden Fixture Loads And Has Expected Categories
    [Tags]    bfcl    fixture    offline
    File Should Exist    ${GOLDEN}
    ${raw}=    Get File    ${GOLDEN}
    Should Contain    ${raw}    "category"
