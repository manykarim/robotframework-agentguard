*** Settings ***
Documentation    Acceptance — research §6.3: PreToolUse hook blocks `rm -rf /`.
Library          AgentGuard    provider=mock

*** Variables ***
${HANDLER}    ${CURDIR}/../../fixtures/hooks/security_check.sh

*** Test Cases ***
PreToolUse Hook Blocks Destructive Bash
    [Tags]    hook    security    phase2
    ${ti}=       Create Dictionary    command=rm -rf /
    ${input}=    Synthesize Hook Input    event=PreToolUse    tool_name=Bash    tool_input=${ti}
    ${result}=   Run Hook Command    handler=${HANDLER}    stdin=${input}
    Hook Should Block    ${result}
    Should Contain    ${result.stderr}    destructive command

PreToolUse Hook Allows Safe Bash
    [Tags]    hook    security    phase2
    ${ti}=       Create Dictionary    command=ls -la
    ${input}=    Synthesize Hook Input    event=PreToolUse    tool_name=Bash    tool_input=${ti}
    ${result}=   Run Hook Command    handler=${HANDLER}    stdin=${input}
    Hook Should Allow    ${result}
