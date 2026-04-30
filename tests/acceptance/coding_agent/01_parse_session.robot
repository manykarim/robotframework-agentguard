*** Settings ***
Documentation    Phase 3 acceptance — parse a Claude Code session JSONL fixture
...              and assert the canonical Session shape (tool calls present,
...              tool responses paired, hook events captured).
Library          AgentGuard    provider=mock

*** Variables ***
${FIXTURE}        ${CURDIR}/../../fixtures/coding_agent/sessions/claude_code_with_tools.jsonl
${MIN_FIXTURE}    ${CURDIR}/../../fixtures/coding_agent/sessions/claude_code_minimal.jsonl


*** Test Cases ***
Parse Claude Code Session With Tools
    [Tags]    coding_agent    session    phase3
    ${session}=    Parse Session JSONL    ${FIXTURE}
    ${tool_calls}=        Get Length    ${session.tool_calls}
    ${tool_responses}=    Get Length    ${session.tool_responses}
    Should Be True    ${tool_calls} > 0
    Should Be True    ${tool_responses} > 0
    Validate Session Schema    ${session}

Parse Minimal Claude Code Session
    [Tags]    coding_agent    session    phase3
    ${session}=    Parse Session JSONL    ${MIN_FIXTURE}
    Should Be Equal As Strings    ${session.id}    synthetic-min-001
    Should Be Equal As Strings    ${session.source}    claude-code

Paired Tool Calls Have Matching IDs
    [Tags]    coding_agent    session    phase3
    ${session}=    Parse Session JSONL    ${FIXTURE}
    ${call_ids}=    Evaluate    {tc.id for tc in $session.tool_calls}
    FOR    ${tr}    IN    @{session.tool_responses}
        Should Be True    "${tr.tool_call_id}" in ${call_ids}    paired tool_call_id missing
    END
