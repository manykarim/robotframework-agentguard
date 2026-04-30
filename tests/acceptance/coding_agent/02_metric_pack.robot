*** Settings ***
Documentation    Phase 3 acceptance — load the bundled "degraded" Session
...              fixture and verify that the #42796 metric pack flags it as
...              ``degraded`` with multiple specific threshold breaches.
Library          AgentGuard    provider=mock
Library          OperatingSystem
Library          Collections

*** Variables ***
${DEGRADED_JSON}    ${CURDIR}/../../fixtures/coding_agent/metrics/degraded_session.json
${HEALTHY_JSON}     ${CURDIR}/../../fixtures/coding_agent/metrics/sample_session.json


*** Test Cases ***
Degraded Session Reports Degraded Health
    [Tags]    coding_agent    metrics    phase3
    ${session}=    Load Degraded Fixture    ${DEGRADED_JSON}
    ${health}=     Get Session Health    ${session}
    Should Be Equal As Strings    ${health}    degraded

Degraded Session Breaches Stop Hook Threshold
    [Tags]    coding_agent    metrics    phase3
    ${session}=    Load Degraded Fixture    ${DEGRADED_JSON}
    ${count}=      Stop Hook Violation Count    ${session}
    Should Be True    ${count} > 0

Degraded Session Breaches User Interrupt Threshold
    [Tags]    coding_agent    metrics    phase3
    ${session}=    Load Degraded Fixture    ${DEGRADED_JSON}
    Run Keyword And Expect Error    *    User Interrupts Per 1K Should Be Below    ${session}    2.0

Healthy Session Reports Healthy Health
    [Tags]    coding_agent    metrics    phase3
    ${session}=    Load Degraded Fixture    ${HEALTHY_JSON}
    ${health}=     Get Session Health    ${session}
    Should Be Equal As Strings    ${health}    healthy

Healthy Session Passes Read Edit Ratio
    [Tags]    coding_agent    metrics    phase3
    ${session}=    Load Degraded Fixture    ${HEALTHY_JSON}
    Read Edit Ratio Should Be Above    ${session}    4.0


*** Keywords ***
Load Degraded Fixture
    [Documentation]    Hydrate a JSON fixture into a Session dataclass via the
    ...                conftest helper. Avoids depending on a not-yet-shipped
    ...                ``Load Session JSON`` keyword.
    [Arguments]    ${path}
    ${session}=    Evaluate    __import__('tests.conftest', fromlist=['load_session_json']).load_session_json($path)
    RETURN    ${session}
