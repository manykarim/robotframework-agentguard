*** Settings ***
Documentation    Acceptance — research §6.3: Stop hook forces tests to pass.
Library          AgentGuard    provider=mock

*** Variables ***
${HANDLER}    ${CURDIR}/../../fixtures/hooks/require_tests.sh

*** Test Cases ***
Stop Hook Forces Test Pass Before Stopping
    [Tags]    hook    stop    phase2
    ${input}=    Synthesize Hook Input    event=Stop    stop_hook_active=${False}
    ${result}=    Run Hook Command    handler=${HANDLER}    stdin=${input}
    Hook Decision Should Be    ${result}    block
    Should Contain    ${result.reason}    Test suite must pass

Stop Hook Honours Stop_Hook_Active Flag
    [Tags]    hook    stop    phase2
    ${input}=    Synthesize Hook Input    event=Stop    stop_hook_active=${True}
    ${result}=    Run Hook Command    handler=${HANDLER}    stdin=${input}
    Hook Should Allow    ${result}
