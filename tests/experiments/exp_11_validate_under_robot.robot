*** Settings ***
Documentation    exp_11 — does AssertionEngine's `validate` operator cover the
...              `between(low, high)` use-case ADR-022 flagged as an operator gap?
...
...              Run via: PYTHONPATH=. uv run robot --outputdir _robot_out
...              tests/experiments/exp_11_validate_under_robot.robot
...
...              Key finding: YES, but `value` MUST be typed (`-> float` / `int`).
...              Robot's positional-arg coercion delivers `str` by default — the
...              real adoption pattern relies on the keyword's typed return.
Library          tests.experiments.exp_11_assertion_helper

*** Variables ***
${LO}    ${0.4}
${HI}    ${0.7}

*** Test Cases ***

# === SCENARIO 1: numeric `between` via `validate` (the ADR-022 gap) ===

Validate Inclusive Range — Value In Range Passes
    [Tags]    exp11    validate    between
    Verify Float    ${0.5}    validate    0.4 <= value <= 0.7

Validate Inclusive Range — Value Below Lower Raises
    [Tags]    exp11    validate    between
    Run Keyword And Expect Error    *0.3*    Verify Float    ${0.3}    validate    0.4 <= value <= 0.7

Validate Inclusive Range — Value Above Upper Raises
    [Tags]    exp11    validate    between
    Run Keyword And Expect Error    *0.8*    Verify Float    ${0.8}    validate    0.4 <= value <= 0.7

Validate Inclusive Range — Lower Boundary Passes
    [Tags]    exp11    validate    between    boundary
    Verify Float    ${0.4}    validate    0.4 <= value <= 0.7

Validate Inclusive Range — Upper Boundary Passes
    [Tags]    exp11    validate    between    boundary
    Verify Float    ${0.7}    validate    0.4 <= value <= 0.7

Validate Exclusive Range — Strict Bounds
    [Tags]    exp11    validate    between
    Verify Int    ${50}    validate    0 < value < 100

# === SCENARIO 2: composite predicates (no native operator) ===

Validate Composite Predicate — Positive AND Even
    [Tags]    exp11    validate    composite
    Verify Int    ${4}    validate    value > 0 and value % 2 == 0

Validate Composite Predicate — Positive Odd Raises
    [Tags]    exp11    validate    composite
    Run Keyword And Expect Error    *    Verify Int    ${3}    validate    value > 0 and value % 2 == 0

Validate With RF Variable Substitution Of Bounds
    [Tags]    exp11    validate    rf-substitution
    # ${LO}/${HI} are typed (${0.4}/${0.7}); RF substitutes BEFORE the string
    # reaches assertionengine, so the eval'd expression is `0.4 <= value <= 0.7`.
    Verify Float    ${0.55}    validate    ${LO} <= value <= ${HI}

Validate With Float Tolerance
    [Tags]    exp11    validate    float-tolerance
    Verify Float    ${1.0000001}    validate    abs(value - 1.0) < 1e-3

# === SCENARIO 3: dict / list / set value shapes ===

Validate List Membership
    [Tags]    exp11    validate    list
    Verify Object    foo    validate    value in ['foo','bar','baz']

Validate Set Containment
    [Tags]    exp11    validate    set
    @{names}=    Create List    add    echo    slow_op
    Verify Object    ${names}    validate    set(['add','echo']).issubset(value)

Validate Dict Field Range
    [Tags]    exp11    validate    dict
    &{stats}=    Create Dictionary    p50=${2.5}    p95=${4.1}    p99=${5.8}
    Verify Object    ${stats}    validate    value['p95'] < value['p99'] * 1.2

# === SCENARIO 4: `then` / `evaluate` returns the expression result ===

Then Returns Evaluated Expression
    [Tags]    exp11    then
    ${returned}=    Verify Int    ${42}    then    value * 2
    Should Be Equal As Numbers    ${returned}    84

Evaluate Is Alias For Then
    [Tags]    exp11    evaluate
    ${returned}=    Verify Int    ${42}    evaluate    value + 1
    Should Be Equal As Numbers    ${returned}    43

# === SCENARIO 5: untyped value gotcha — proves the type-discipline finding ===

Untyped Numeric Comparison Fails — Documents The Gotcha
    [Tags]    exp11    type-coercion
    # Robot delivers ``0.5`` as STRING; the eval becomes "0.4 <= '0.5' <= 0.7"
    # which is a TypeError. Documents why every Get-style keyword in AgentGuard
    # MUST declare its return type so AssertionEngine sees a real Python value.
    Run Keyword And Expect Error    *TypeError*
    ...    Verify Untyped    0.5    validate    0.4 <= value <= 0.7

# === SCENARIO 6: range checks across multiple AgentGuard semantics ===

Tool Call Count Between Two And Five
    [Tags]    exp11    validate    agentguard
    Verify Int    ${3}    validate    2 <= value <= 5

Latency P95 Between 50 And 200 ms
    [Tags]    exp11    validate    agentguard
    Verify Float    ${127.4}    validate    50.0 <= value <= 200.0

Hit Rate Within Acceptance Band
    [Tags]    exp11    validate    agentguard
    Verify Float    ${0.85}    validate    0.7 <= value <= 0.95
