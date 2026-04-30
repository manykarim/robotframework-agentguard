*** Settings ***
Documentation    Phase 3 acceptance — drive the LocalDriver offline (mock
...              provider) and assert the JSONL session file is written.
Library          AgentGuard    provider=mock
Library          OperatingSystem


*** Test Cases ***
Local Driver Writes Session JSONL Offline
    [Tags]    coding_agent    driver    phase3
    ${jsonl}=    Set Variable    ${OUTPUT_DIR}/local-driver-offline.jsonl
    ${result}=    Run Local Driver With Mock    Hello there.    ${jsonl}
    File Should Exist    ${jsonl}
    ${size}=    Get File Size    ${jsonl}
    Should Be True    ${size} > 0

Local Driver Result Has Session Attached
    [Tags]    coding_agent    driver    phase3
    ${jsonl}=    Set Variable    ${OUTPUT_DIR}/local-driver-attached.jsonl
    ${result}=    Run Local Driver With Mock    Say hi.    ${jsonl}
    Should Not Be Equal    ${result.session}    ${None}
    Should Be Equal As Integers    ${result.exit_code}    0


*** Keywords ***
Run Local Driver With Mock
    [Arguments]    ${prompt}    ${jsonl_path}
    ${result}=    Evaluate
    ...    __import__('tests.acceptance.coding_agent._local_driver_helpers', fromlist=['run']).run($prompt, $jsonl_path)
    RETURN    ${result}
