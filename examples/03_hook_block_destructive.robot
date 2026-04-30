*** Settings ***
Documentation    Phase-2 example mirroring research §6.3 — Hook policy enforcement.
...
...              - PreToolUse hook blocks `rm -rf /` (security_check.sh).
...              - Stop hook forces test pass before stopping (require_tests.sh).
...              - Inject-context hook demonstrates `Hook Should Inject Context`.
...
...              All three handlers are real shell scripts in tests/fixtures/hooks/
...              and run offline (no network, no LLM API key required).
Library          AgentGuard
Library          Collections
Library          OperatingSystem

*** Variables ***
${HOOK_DIR}            ${CURDIR}/../tests/fixtures/hooks
${SECURITY_HOOK}       ${HOOK_DIR}/security_check.sh
${REQUIRE_TESTS_HOOK}  ${HOOK_DIR}/require_tests.sh
${INJECT_HOOK}         ${HOOK_DIR}/inject_context.sh
${LOOP_TRAP_HOOK}      ${HOOK_DIR}/loop_trap.sh
${DESTRUCTIVE_CMD}     rm -rf /

*** Test Cases ***
PreToolUse Hook Blocks Destructive Bash
    [Documentation]    research §6.3 — exit-2 = block, even with allow stdout.
    [Tags]             hooks    security    phase2
    ${tool_input}=     Create Dictionary    command=${DESTRUCTIVE_CMD}
    ${envelope}=       Synthesize Hook Input    event=PreToolUse
    ...                tool_name=Bash    tool_input=${tool_input}
    ${result}=         Run Hook Command    handler=${SECURITY_HOOK}    stdin=${envelope}
    Hook Should Block  ${result}
    Should Contain     ${result.stderr}    destructive command

Stop Hook Forces Test Pass Before Stopping
    [Documentation]    research §6.3 — Stop hook blocks until tests pass.
    [Tags]             hooks    stop    phase2
    ${envelope}=       Synthesize Hook Input    event=Stop    stop_hook_active=${False}
    ${result}=         Run Hook Command    handler=${REQUIRE_TESTS_HOOK}    stdin=${envelope}
    Hook Decision Should Be    ${result}    block
    Should Contain     ${result.decision.reason}    Test suite must pass

Stop Hook Honours stop_hook_active And Allows
    [Documentation]    Anti-loop guard: when the active flag is set, allow.
    [Tags]             hooks    stop    loop-safety    phase2
    ${envelope}=       Synthesize Hook Input    event=Stop    stop_hook_active=${True}
    ${result}=         Run Hook Command    handler=${REQUIRE_TESTS_HOOK}    stdin=${envelope}
    Hook Should Allow  ${result}

Inject Context Hook Adds Read-Only Notice
    [Documentation]    Demonstrates `Hook Should Inject Context` against a
    ...                command-handler that emits `additional_context`.
    [Tags]             hooks    inject-context    phase2
    ${tool_input}=     Create Dictionary    file_path=/etc/passwd    new_string=hacked
    ${envelope}=       Synthesize Hook Input    event=PreToolUse
    ...                tool_name=Edit    tool_input=${tool_input}
    ${result}=         Run Hook Command    handler=${INJECT_HOOK}    stdin=${envelope}
    Hook Should Allow  ${result}
    Hook Should Inject Context    ${result}    contains=read-only system path

Detect Stop Hook Loop From Repeated Blocks
    [Documentation]    5 consecutive Stop blocks while stop_hook_active=True
    ...                must trip the loop detector. Uses loop_trap.sh which
    ...                blocks unconditionally — the canonical antipattern.
    [Tags]             hooks    loop-safety    phase2
    ${results}=        Create List
    FOR    ${i}    IN RANGE    5
        ${envelope}=    Synthesize Hook Input    event=Stop    stop_hook_active=${True}
        ${one}=         Run Hook Command    handler=${LOOP_TRAP_HOOK}    stdin=${envelope}
        Append To List  ${results}    ${one}
    END
    Run Keyword And Expect Error    *Stop-hook loop*    Detect Stop Hook Loop    ${results}    window=5
