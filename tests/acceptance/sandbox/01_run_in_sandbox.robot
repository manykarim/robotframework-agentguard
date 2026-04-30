*** Settings ***
Documentation    Acceptance — sandbox: Run a tiny container in Docker.
...              Tagged `docker` so default-offline runs skip cleanly when
...              the daemon (or a permissive host kernel) is unavailable.
Library          AgentGuard    provider=mock
Library          ${CURDIR}/sandbox_helper.py

*** Test Cases ***
Run Echo Hello In Docker Sandbox
    [Tags]    sandbox    docker    phase2
    Skip If Docker Unavailable
    ${result}=    Run In Docker Sandbox    python -c print('hello sandbox')
    Skip If Capdrop Refuses Exec    ${result}
    Should Be Equal As Integers    ${result.exit_code}    0
    Should Contain    ${result.stdout}    hello sandbox
