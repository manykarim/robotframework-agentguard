"""Operator-inventory parity test for the AssertionEngine shared kernel.

Per ADR-022 and ``docs/research/assertion-engine.md``: AssertionEngine ships
**13 distinct operators reachable via 26 alias keys** in a functional
``Enum(...)``. AgentGuard's :func:`coerce_operator` is the only place we
translate between alias-strings and the enum; this module pins that
translation contract so a future AssertionEngine release that renames an
alias is caught as a test failure rather than a silent runtime bug.

The 13 distinct members (per ``set(AssertionOperator)`` against
``robotframework-assertion-engine 4.0.x``) are:

    ==/equal/equals/should be
    !=/inequal/should not be
    </less than
    <=
    >/greater than
    >=
    *=/contains
    not contains
    ^=/starts/should start with
    $=/ends/should end with
    matches
    validate
    then/evaluate
"""

from __future__ import annotations

import pytest

from AgentGuard._assertions import AssertionOperator, coerce_operator

# Distinct enum members (the 13-name set ADR-022 promises). We materialise it
# from the live enum so a future upstream that adds a new member fails this
# test loudly rather than silently passing under a stale hard-coded list.
DISTINCT_MEMBERS: list[AssertionOperator] = sorted(set(AssertionOperator), key=lambda m: m.name)

# All alias keys (26 in 4.0.x).
ALL_ALIASES: list[str] = list(AssertionOperator.__members__.keys())


# ---------------------------------------------------------------------------
# Inventory contract.
# ---------------------------------------------------------------------------


def test_thirteen_distinct_operators_are_present() -> None:
    """ADR-022 promises 13 distinct enum members; pin the count."""
    assert len(DISTINCT_MEMBERS) == 13, sorted(m.name for m in DISTINCT_MEMBERS)


def test_total_alias_count_is_at_least_thirteen() -> None:
    """At minimum there's one alias per distinct member; in practice there are 26."""
    assert len(ALL_ALIASES) >= len(DISTINCT_MEMBERS)


# ---------------------------------------------------------------------------
# Reachability — every distinct operator can be coerced from its canonical name.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("member", DISTINCT_MEMBERS)
def test_every_distinct_operator_is_reachable_via_canonical_name(
    member: AssertionOperator,
) -> None:
    """``coerce_operator(member.name)`` returns the same enum member."""
    coerced = coerce_operator(member.name)
    assert coerced is member, f"coerce_operator({member.name!r}) returned {coerced!r}, expected {member!r}"


@pytest.mark.parametrize("member", DISTINCT_MEMBERS)
def test_every_distinct_operator_round_trips_via_enum(
    member: AssertionOperator,
) -> None:
    """Passing the enum directly returns the same enum member."""
    assert coerce_operator(member) is member


@pytest.mark.parametrize("alias", ALL_ALIASES)
def test_every_alias_resolves_to_a_member(alias: str) -> None:
    """Every alias listed by the upstream Enum maps to *some* distinct member."""
    member = coerce_operator(alias)
    assert member is not None
    assert member in DISTINCT_MEMBERS


# ---------------------------------------------------------------------------
# Specific aliases the docs call out — pin the canonical resolution targets.
# ---------------------------------------------------------------------------


def test_alias_equals_resolves_to_equal_member() -> None:
    """``coerce_operator('equals')`` resolves to the canonical ``==``/``equal``
    member — not a separate one."""
    assert coerce_operator("equals") is AssertionOperator["=="]
    assert coerce_operator("equals") is AssertionOperator["equal"]


def test_aliases_then_and_evaluate_resolve_to_same_member() -> None:
    """``then`` and ``evaluate`` are documented as aliases for the same member.

    AgentGuard's docs (``docs/research/assertion-engine.md``) list both as
    referring to the Python-expression evaluator. Confirm they collapse here.
    """
    then = coerce_operator("then")
    evaluate = coerce_operator("evaluate")
    assert then is evaluate
    assert then is AssertionOperator.then


def test_double_equals_alias_resolves_to_equal() -> None:
    assert coerce_operator("==") is AssertionOperator.equal


def test_should_be_alias_resolves_to_equal() -> None:
    """``should be`` is documented as a human-readable alias for ``==``."""
    assert coerce_operator("should be") is AssertionOperator.equal


def test_should_not_be_alias_resolves_to_inequal() -> None:
    assert coerce_operator("should not be") is AssertionOperator.inequal


def test_bang_equal_alias_resolves_to_inequal() -> None:
    assert coerce_operator("!=") is AssertionOperator.inequal


def test_star_equal_alias_resolves_to_contains() -> None:
    """``*=`` is the Browser-Library shorthand for ``contains``."""
    assert coerce_operator("*=") is AssertionOperator.contains


def test_caret_equal_alias_resolves_to_starts() -> None:
    assert coerce_operator("^=") is AssertionOperator.starts


def test_dollar_equal_alias_resolves_to_ends() -> None:
    assert coerce_operator("$=") is AssertionOperator.ends


def test_validate_does_not_share_a_member_with_then() -> None:
    """`validate` and `then` are *different* members — important because
    AgentGuard's `validate` gate (ACL Rule B) only fires for `validate`,
    not for `then`."""
    assert coerce_operator("validate") is not coerce_operator("then")
    assert coerce_operator("validate") is AssertionOperator.validate
