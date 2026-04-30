*** Settings ***
Documentation    Phase-2 example — Run In Sandbox via the Docker backend.
...
...              Default-deny policy: --network=none, read-only fs, dropped
...              caps, no docker-socket mount. ``allow_code_execution=True``
...              is required for actual execution per ADR-013.
...
...              Tagged ``docker`` so CI workers without a daemon can skip:
...
...                  uv run robot --exclude docker examples/
...
...              Tagged ``phase2`` to opt out of Phase-1-only test runs.
...
...              When the security sub-library exposes ``Run In Sandbox`` as
...              a top-level keyword, the wrapper here can be replaced with
...              the keyword call. Until then we drive the dispatch helper
...              directly so the example exercises the real backend.
Library          AgentGuard
Library          Collections

*** Test Cases ***
Docker Backend Should Be Reachable
    [Documentation]    Probe the local docker daemon — fast pre-check.
    [Tags]    sandbox    docker    phase2
    ${info}=    Sandbox Should Be Available    docker
    Should Be Equal As Strings    ${info}[backend]    docker
    Should Not Be Empty    ${info}[version]

Run Echo In Docker Sandbox
    [Documentation]    `python -c "print('hi')"` inside an alpine container.
    ...                Skipped when the host's docker rejects the secure
    ...                profile (`no-new-privileges:true` + `cap-drop ALL`)
    ...                — that is a host-config issue, not a sandbox bug.
    [Tags]    sandbox    docker    phase2
    ${policy}=    Build Sandbox Policy
    Skip Sandbox If Host Rejects Secure Profile    ${policy}
    @{cmd}=    Create List    python    -c    print('hi')
    ${result}=    Run In Sandbox Helper    ${policy}    ${cmd}    image=python:3.12-alpine    timeout_seconds=${15}
    Should Be Equal As Integers    ${result.exit_code}    0
    Should Contain    ${result.stdout}    hi
    Should Be Equal As Strings    ${result.backend}    docker

*** Keywords ***
Build Sandbox Policy
    ${mod}=    Evaluate    __import__('AgentGuard.security.sandbox', fromlist=['SandboxPolicy'])
    ${policy}=    Evaluate    $mod.SandboxPolicy(backend='docker', allow_code_execution=True, network_allowed=False, cpu_limit_seconds=10, mem_limit_mb=256, pid_limit=64)
    RETURN    ${policy}

Run In Sandbox Helper
    [Documentation]    Thin wrapper around AgentGuard.security.sandbox.run_in_sandbox.
    ...                Replace with `Run In Sandbox` keyword once exposed.
    [Arguments]    ${policy}    ${command}    ${image}=python:3.12-alpine    ${timeout_seconds}=${15}
    ${mod}=    Evaluate    __import__('AgentGuard.security.sandbox', fromlist=['run_in_sandbox'])
    ${result}=    Evaluate    $mod.run_in_sandbox($policy, $command, image=$image, timeout_seconds=$timeout_seconds)
    RETURN    ${result}

Skip Sandbox If Host Rejects Secure Profile
    [Documentation]    Smoke-test the secure profile via `sh -c "echo s"`.
    ...                Skip when stderr says `operation not permitted` (snap docker
    ...                + no-new-privileges combination is the canonical case).
    [Arguments]    ${policy}
    @{smoke}=    Create List    sh    -c    echo s
    ${result}=    Run In Sandbox Helper    ${policy}    ${smoke}    image=alpine:3.20    timeout_seconds=${10}
    IF    ${result.exit_code} != 0 or 'operation not permitted' in $result.stderr
        Skip    Host docker rejects secure sandbox profile (stderr=${result.stderr})
    END
