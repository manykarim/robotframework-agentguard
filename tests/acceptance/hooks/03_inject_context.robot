*** Settings ***
Documentation    Acceptance — research §6.3: Hook injects additional_context.
Library          AgentGuard    provider=mock

*** Variables ***
${HANDLER}    ${CURDIR}/../../fixtures/hooks/inject_context.sh

*** Test Cases ***
Hook Injects Additional Context String
    [Tags]    hook    inject    phase2
    ${input}=    Synthesize Hook Input
    ...    event=PreToolUse
    ...    tool_name=Edit
    ...    tool_input={"file_path": "/etc/passwd"}
    ${result}=    Run Hook Command    handler=${HANDLER}    stdin=${input}
    Hook Should Allow    ${result}
    Hook Should Inject Context    ${result}    contains=read-only system path
