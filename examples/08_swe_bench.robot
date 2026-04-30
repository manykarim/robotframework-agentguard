*** Settings ***
Documentation    Phase-3 example — SWE-bench loader smoke test.
...
...              Loads the SWE-bench Verified split (or the bundled mini-fixture
...              when the ``[benchmarks]`` extra / ``datasets`` package is not
...              installed). Iterates one task and asserts the loader returned
...              a populated ``Task`` dataclass.
...
...              This is **not** a real SWE-bench eval — running the upstream
...              ``test_cmd`` against the agent's patch inside the upstream
...              Docker image is Phase-4 work (see ``docs/PLAN.md`` §8 Phase 4).
...              The point here is to demonstrate the keyword wiring + the
...              fixture-fallback contract.
...
...              Tagged ``slow`` so default unit-test runs skip it.
Library          AgentGuard
Library          AgentGuard.coding_agent.benchmarks.library.CodingBenchmarkKeywords    WITH NAME    Bench
Library          Collections

*** Test Cases ***
Load SWE Bench Returns A Populated Task Dataclass
    [Documentation]    Smoke — verify the loader returns ≥1 ``Task`` with
    ...                non-empty ``id`` and ``prompt`` fields.
    [Tags]    coding-agent    benchmark    swe-bench    slow    phase3
    ${tasks}=    Bench.Load SWE Bench Dataset    limit=1
    ${count}=    Get Length    ${tasks}
    Should Be True    ${count} >= 1    SWE-bench loader returned 0 tasks
    ${task}=    Set Variable    ${tasks}[0]
    Should Not Be Empty    ${task.id}
    Should Not Be Empty    ${task.prompt}
    Log    loaded task ${task.id} (${count} total)
