*** Settings ***
Documentation    Phase-3 example — HumanEval live OpenRouter smoke.
...
...              Drives the LocalDriver against ``openrouter/openai/gpt-4o-mini``
...              for a single HumanEval task and verifies the wiring produces a
...              scoreable ``RunResult``. Threshold is **0.0** because this is
...              a wiring smoke, not a model-quality benchmark — gpt-4o-mini
...              against a single task is not representative of pass@1 quality
...              in any sense, and HumanEval is a leaked-into-pretraining set
...              anyway (research §2.5).
...
...              For a real evaluation pass a larger ``limit=`` and use the
...              ``Run Benchmark Suite`` keyword which loops + scores in one
...              shot. For canary regression gating prefer the
...              ``Behavioral Report Should Match Baseline`` flow over public
...              benchmarks (research §2.6, §6.5).
...
...              Tagged ``live`` — opted-out by default in CI.
Library          AgentGuard
Library          AgentGuard.coding_agent.benchmarks.library.CodingBenchmarkKeywords    WITH NAME    Bench
Library          Collections
Library          OperatingSystem

Suite Setup      Skip If Live Disabled

*** Keywords ***
Skip If Live Disabled
    [Documentation]    Skip the suite when ``OPENROUTER_API_KEY`` is unset.
    ${api_key}=    Get Environment Variable    OPENROUTER_API_KEY    ${EMPTY}
    Skip If    "${api_key}" == "${EMPTY}"    OPENROUTER_API_KEY missing — live HumanEval smoke skipped

*** Test Cases ***
HumanEval One Task End To End Via LocalDriver
    [Documentation]    Single-task wiring smoke against ``openrouter/openai/gpt-4o-mini``.
    [Tags]    coding-agent    benchmark    humaneval    live    phase3
    ${tasks}=    Bench.Load HumanEval Dataset    limit=1
    ${count}=    Get Length    ${tasks}
    Should Be True    ${count} >= 1    HumanEval loader returned 0 tasks
    ${task}=    Set Variable    ${tasks}[0]
    ${result}=   Bench.Run HumanEval Task
    ...    task=${task}
    ...    driver=local
    ...    model=openrouter/openai/gpt-4o-mini
    ${results}=    Create List    ${result}
    Bench.HumanEval Pass At K Should Be Above    results=${results}    k=1    threshold=-0.001
