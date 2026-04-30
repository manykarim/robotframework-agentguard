*** Settings ***
Documentation    Phase 3 acceptance — live HumanEval 1-task smoke test against
...              OpenRouter ``gpt-4o-mini``. Tagged ``live`` so default-offline
...              runs (no OPENROUTER_API_KEY) skip cleanly.
Library          AgentGuard    provider=mock
Library          OperatingSystem


*** Test Cases ***
HumanEval Smoke One Task Live
    [Tags]    coding_agent    benchmark    live    phase3
    Skip If    "%{OPENROUTER_API_KEY=}" == ""    live test requires OPENROUTER_API_KEY
    ${score}=    Run HumanEval Smoke
    Should Be True    ${score}[n] >= 1
    Should Be True    0 <= ${score}[pass_at_1] <= 1


*** Keywords ***
Run HumanEval Smoke
    [Documentation]    One-task HumanEval smoke. Uses the bundled mini-fixture
    ...                so no network dependency on HuggingFace; only the LLM
    ...                call hits OpenRouter.
    ${score}=    Evaluate
    ...    __import__('tests.acceptance.coding_agent._humaneval_helpers', fromlist=['run']).run()
    RETURN    ${score}
