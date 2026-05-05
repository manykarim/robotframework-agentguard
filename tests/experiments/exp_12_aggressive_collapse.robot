*** Settings ***
Documentation    exp_12 — can the analyst's "edge cases that resist collapse"
...              actually fold into AssertionEngine via `validate` / `evaluate`?
...              Goal: prove or refute the aggressive-collapse path so ADR-022
...              can pick the right final count under the no-deprecation strategy.
...
...              Run: PYTHONPATH=. uv run robot --outputdir _robot_out
...              tests/experiments/exp_12_aggressive_collapse.robot
Library          tests.experiments.exp_11_assertion_helper
Library          tests.experiments.exp_12_resistant_helper

*** Test Cases ***

# === GROUP A: Mann-Whitney U — does (statistic, pvalue) compose via validate? ===

MW U Tuple Result — validate p-value via index access
    [Tags]    exp12    mw-u    tuple
    ${tuple}=    Synthesize MW Result    statistic=541.0    pvalue=0.03
    Verify Object    ${tuple}    validate    value[1] < 0.05

MW U Tuple Result — high p-value fails
    [Tags]    exp12    mw-u    tuple
    ${tuple}=    Synthesize MW Result    statistic=541.0    pvalue=0.42
    Run Keyword And Expect Error    *    Verify Object    ${tuple}    validate    value[1] < 0.05

MW U Dataclass — validate via attribute access
    [Tags]    exp12    mw-u    dataclass
    ${result}=    Synthesize MW Dataclass    statistic=541.0    pvalue=0.03    alternative=greater
    Verify Object    ${result}    validate    value.pvalue < 0.05

MW U Dataclass — composite predicate (p < α AND U significant)
    [Tags]    exp12    mw-u    composite
    ${result}=    Synthesize MW Dataclass    statistic=541.0    pvalue=0.03    alternative=greater
    Verify Object    ${result}    validate    value.pvalue < 0.05 and value.statistic > 100

# === GROUP B: Hook Decision — does == replace Hook Should Block? ===

Hook Should Block Replacement — Get Hook Decision == block
    [Tags]    exp12    hook    block
    ${decision}=    Set Variable    block
    Verify Object    ${decision}    ==    block

Hook Should Allow Replacement — Get Hook Decision != block
    [Tags]    exp12    hook    allow
    ${decision}=    Set Variable    allow
    Verify Object    ${decision}    !=    block

# === GROUP C: Should Not Call Any Tool — list emptiness via validate ===

Should Not Call Any Tool Replacement — len(value) == 0 via validate
    [Tags]    exp12    tool-calls    empty
    @{calls}=    Create List
    Verify Object    ${calls}    validate    len(value) == 0

Should Not Call Any Tool — non-empty fails
    [Tags]    exp12    tool-calls    empty
    @{calls}=    Create List    add
    Run Keyword And Expect Error    *    Verify Object    ${calls}    validate    len(value) == 0

# === GROUP D: Required Tool With Params — set comprehension via validate ===

Required Params — every call carries level=INFO
    [Tags]    exp12    required-params
    ${calls}=    Synthesize Tool Calls
    ...    {"name":"log","arguments":{"level":"INFO","msg":"a"}}
    ...    {"name":"log","arguments":{"level":"INFO","msg":"b"}}
    Verify Object    ${calls}    validate    all(c.get('arguments',{}).get('level') == 'INFO' for c in value if c.get('name') == 'log')

Required Params — one call misses param fails
    [Tags]    exp12    required-params
    ${calls}=    Synthesize Tool Calls
    ...    {"name":"log","arguments":{"level":"INFO","msg":"a"}}
    ...    {"name":"log","arguments":{"level":"DEBUG","msg":"b"}}
    Run Keyword And Expect Error    *
    ...    Verify Object    ${calls}    validate    all(c.get('arguments',{}).get('level') == 'INFO' for c in value if c.get('name') == 'log')

# === GROUP E: Tool Sequence Should Match — ordered subsequence via validate ===

Tool Sequence Subsequence — exact match via validate
    [Tags]    exp12    sequence
    @{names}=    Create List    plan    weather    places    summary
    Verify Object    ${names}    validate    value.index('weather') < value.index('places')

Tool Sequence Subsequence — wildcard removed via list filter
    [Tags]    exp12    sequence    wildcard
    @{names}=    Create List    plan    misc    weather    misc    places
    Verify Object    ${names}    validate    [n for n in value if n in {'weather','places'}] == ['weather','places']

# === GROUP F: Composite report — Skill Security Scan readability test ===

Scan Skill Decision — pass via decision attribute
    [Tags]    exp12    scan    composite
    ${report}=    Synthesize Skill Report    decision=allow    critical_findings=0
    Verify Object    ${report}    validate    value.decision != 'deny' and value.critical_findings == 0

Scan Skill Decision — deny on critical fails
    [Tags]    exp12    scan    composite
    ${report}=    Synthesize Skill Report    decision=deny    critical_findings=1
    Run Keyword And Expect Error    *
    ...    Verify Object    ${report}    validate    value.decision != 'deny' and value.critical_findings == 0

# === GROUP G: Sandbox Exit Code Should Be — already trivially collapses to == ===

Sandbox Exit Code — value-object access via validate
    [Tags]    exp12    sandbox    exit
    ${result}=    Synthesize Sandbox Result    exit_code=0    stdout=ok
    Verify Object    ${result}    validate    value.exit_code == 0

# === GROUP H: BOUNDARY — Bootstrap CI containment readability ===

Bootstrap CI Contains Expected — via dict-attribute compare
    [Tags]    exp12    stats    ci
    ${ci}=    Synthesize CI    low=0.4    high=0.7
    Verify Object    ${ci}    validate    value['low'] <= 0.55 <= value['high']
