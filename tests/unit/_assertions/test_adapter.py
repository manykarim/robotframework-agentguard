"""Unit coverage for ``AgentGuard._assertions.adapter``.

ADR-022 §"Phase 4-D — One-Shot Replacement" promises a single canonical entry
point — :func:`assert_value` — that every Get-style keyword routes through.
This module pins that contract:

- Pass-through when ``assertion_operator is None`` (the keyword still returns
  its computed value).
- Every operator family delegates to ``assertionengine.verify_assertion``
  (we do not re-implement the comparison; we just gate it).
- ACL Rule A: polling on Tier-2/3 keywords raises ``PollingDisallowedError``
  (ADR-019, ADR-022 negative consequence).
- ACL Rule B: ``validate`` is disabled by default and raises
  ``ValidateOperatorDisallowed`` (ADR-013).
- The :class:`AssertionAdapter` class wraps the same calls for stateful
  configuration (currently no sub-library binds it; tests assert the wrapper
  shape so future adopters have a regression net).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from AgentGuard._assertions import (
    AssertionAdapter,
    AssertionOperator,
    PollingDisallowedError,
    ValidateOperatorDisallowed,
    assert_value,
    coerce_operator,
)

# ---------------------------------------------------------------------------
# Pass-through (operator is None)
# ---------------------------------------------------------------------------


class TestPassThrough:
    def test_operator_none_returns_value_unchanged(self) -> None:
        assert assert_value(5, None) == 5

    def test_operator_none_returns_complex_value_unchanged(self) -> None:
        sentinel: dict[str, Any] = {"a": 1, "b": [2, 3]}
        assert assert_value(sentinel, None) is sentinel

    def test_pass_through_does_not_call_verify_assertion(self) -> None:
        # Belt-and-braces: when operator is None we must NOT invoke the
        # underlying verify_assertion (it would still pass for value-only,
        # but it carries telemetry side-effects on some integrations).
        with patch("AgentGuard._assertions.adapter._verify_assertion") as m:
            assert_value(42, None) == 42  # noqa: B015 — assertion intentional
            assert m.call_count == 0


# ---------------------------------------------------------------------------
# Scalar operators — delegated to AssertionEngine.
# ---------------------------------------------------------------------------


class TestScalarOperators:
    def test_ge_passes(self) -> None:
        assert assert_value(5, ">=", 3) == 5

    def test_ge_passes_at_boundary(self) -> None:
        assert assert_value(3, ">=", 3) == 3

    def test_le_fails_when_value_greater(self) -> None:
        with pytest.raises(AssertionError):
            assert_value(5, "<=", 3)

    def test_eq_passes(self) -> None:
        assert assert_value(5, "==", 5) == 5

    def test_eq_fails(self) -> None:
        with pytest.raises(AssertionError):
            assert_value(5, "==", 4)

    def test_lt_passes(self) -> None:
        assert assert_value(2, "<", 3) == 2

    def test_gt_passes(self) -> None:
        assert assert_value(4, ">", 3) == 4

    def test_neq_passes(self) -> None:
        assert assert_value(5, "!=", 4) == 5


# ---------------------------------------------------------------------------
# String operators — `*=` (contains), `^=` (starts), `$=` (ends), `matches`.
# ---------------------------------------------------------------------------


class TestStringOperators:
    def test_contains_passes(self) -> None:
        # AssertionEngine's `verify_assertion` returns the input value on success
        # for value-comparison operators; pin that contract too.
        assert assert_value("foobar", "*=", "oo") == "foobar"

    def test_contains_fails(self) -> None:
        with pytest.raises(AssertionError):
            assert_value("foobar", "*=", "zzz")

    def test_starts_passes(self) -> None:
        assert assert_value("foobar", "^=", "foo") == "foobar"

    def test_ends_passes(self) -> None:
        assert assert_value("foobar", "$=", "bar") == "foobar"

    def test_matches_passes(self) -> None:
        # AssertionEngine uses `re.search`, not `re.fullmatch`.
        assert assert_value("foo123bar", "matches", r"\d+") == "foo123bar"

    def test_not_contains_passes(self) -> None:
        assert assert_value("foobar", "not contains", "zzz") == "foobar"


# ---------------------------------------------------------------------------
# `validate` operator — disabled by default (ACL Rule B).
# ---------------------------------------------------------------------------


class TestValidateGate:
    def test_validate_disabled_by_default(self) -> None:
        with pytest.raises(ValidateOperatorDisallowed):
            assert_value(0.5, "validate", "0.4 <= value <= 0.7")

    def test_validate_disabled_via_enum(self) -> None:
        # Pass the enum directly to confirm the gate keys off the enum value,
        # not the string spelling.
        with pytest.raises(ValidateOperatorDisallowed):
            assert_value(0.5, AssertionOperator.validate, "0.4 <= value <= 0.7")

    def test_validate_disallowed_error_message_is_actionable(self) -> None:
        with pytest.raises(ValidateOperatorDisallowed) as excinfo:
            assert_value(0.5, "validate", "True")
        assert "ADR-013" in str(excinfo.value)

    def test_validate_with_allow_validate_routes_to_engine(self) -> None:
        # When `allow_validate=True`, AssertionEngine's `verify_assertion` runs
        # the Python expression via `BuiltIn().evaluate()`. Outside a Robot
        # context that raises ``RobotNotRunningError``; we mock it so the test
        # is hermetic but still proves our gate stops blocking. Use the *full*
        # qualified import path so we patch what `verify_assertion` reads.
        with patch("AgentGuard._assertions.adapter._verify_assertion") as mock_verify:
            mock_verify.return_value = 0.5
            result = assert_value(0.5, "validate", "0.4 <= value <= 0.7", allow_validate=True)
        assert result == 0.5
        # Confirm we delegated, with the resolved enum.
        assert mock_verify.call_count == 1
        args, kwargs = mock_verify.call_args
        assert args[1] is AssertionOperator.validate


# ---------------------------------------------------------------------------
# Polling gate — ACL Rule A.
# ---------------------------------------------------------------------------


class TestPollingGate:
    def test_polling_rejected_for_tier_2(self) -> None:
        with pytest.raises(PollingDisallowedError):
            assert_value(5, ">=", 3, tier=2, polling=1.0)

    def test_polling_rejected_for_tier_3(self) -> None:
        with pytest.raises(PollingDisallowedError):
            assert_value(5, ">=", 3, tier=3, polling=0.5)

    def test_polling_allowed_for_tier_1(self) -> None:
        # Tier-1 keywords MAY poll (no LLM cost compounding).
        assert assert_value(5, ">=", 3, tier=1, polling=1.0) == 5

    def test_no_polling_allowed_for_tier_2(self) -> None:
        # Without polling, Tier-2 keywords work fine.
        assert assert_value(5, ">=", 3, tier=2) == 5

    def test_polling_disallowed_message_points_at_stats(self) -> None:
        with pytest.raises(PollingDisallowedError) as excinfo:
            assert_value(5, ">=", 3, tier=2, polling=1.0)
        # The remediation pointer must mention the explicit re-sample escape
        # hatch — Stats' Run N Times / Pass At K Should Be Above.
        msg = str(excinfo.value)
        assert "Stats" in msg or "Run N Times" in msg


# ---------------------------------------------------------------------------
# coerce_operator — accepts enum, alias, or None.
# ---------------------------------------------------------------------------


class TestCoerceOperator:
    def test_returns_none_for_none_input(self) -> None:
        assert coerce_operator(None) is None

    def test_returns_enum_when_given_enum(self) -> None:
        assert coerce_operator(AssertionOperator.equal) is AssertionOperator.equal

    def test_resolves_symbolic_alias(self) -> None:
        # ``>=`` is its own enum member (distinct from ``>`` / ``greater than``);
        # the symbol-table for AssertionEngine 4.x lists it explicitly.
        assert coerce_operator(">=") is AssertionOperator[">="]

    def test_resolves_canonical_name(self) -> None:
        assert coerce_operator("equal") is AssertionOperator.equal

    def test_alias_gt_resolves_to_greater_than(self) -> None:
        # ``>`` (alone) and ``greater than`` are aliases of the same member.
        assert coerce_operator(">") is AssertionOperator["greater than"]
        assert coerce_operator("greater than") is AssertionOperator["greater than"]

    def test_unknown_alias_raises_value_error(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            coerce_operator("totally-bogus")
        # Error message must list the valid options so the user can self-recover.
        assert "Valid:" in str(excinfo.value)

    def test_alias_equals_resolves_to_double_equals(self) -> None:
        assert coerce_operator("equals") is AssertionOperator["=="]
        assert coerce_operator("equals") is AssertionOperator.equal

    def test_alias_then_resolves_to_evaluate_member(self) -> None:
        # AssertionEngine ships `then` and `evaluate` as two aliases pointing
        # at the same enum member (`then`, the Python-expression evaluator).
        assert coerce_operator("then") is AssertionOperator.then
        assert coerce_operator("evaluate") is AssertionOperator.then


# ---------------------------------------------------------------------------
# AssertionAdapter — class-shaped wrapper around assert_value.
# ---------------------------------------------------------------------------


class TestAssertionAdapter:
    def test_default_construction(self) -> None:
        ad = AssertionAdapter()
        assert ad.tier == 1
        assert ad.allow_validate is False

    def test_verify_pass_through(self) -> None:
        ad = AssertionAdapter()
        assert ad.verify(7) == 7

    def test_verify_with_operator(self) -> None:
        ad = AssertionAdapter()
        assert ad.verify(7, ">=", 3) == 7

    def test_verify_failing_assertion(self) -> None:
        ad = AssertionAdapter()
        with pytest.raises(AssertionError):
            ad.verify(7, "<=", 3)

    def test_tier_binds_polling_gate(self) -> None:
        ad = AssertionAdapter(tier=2)
        with pytest.raises(PollingDisallowedError):
            ad.verify(5, ">=", 3, polling=1.0)

    def test_allow_validate_flag_bypasses_gate(self) -> None:
        ad = AssertionAdapter(allow_validate=True)
        with patch("AgentGuard._assertions.adapter._verify_assertion") as mock_verify:
            mock_verify.return_value = 0.5
            ad.verify(0.5, "validate", "0.4 <= value <= 0.7")
        assert mock_verify.call_count == 1


# ---------------------------------------------------------------------------
# Smoke: the public surface re-exports the documented symbols. Catches the
# regression where a future refactor of `__init__.py` accidentally drops one.
# ---------------------------------------------------------------------------


class TestPublicSurface:
    def test_module_reexports(self) -> None:
        from AgentGuard import _assertions  # noqa: PLC0415

        for name in (
            "AssertionAdapter",
            "AssertionOperator",
            "PollingDisallowedError",
            "ValidateOperatorDisallowed",
            "assert_value",
            "coerce_operator",
        ):
            assert hasattr(_assertions, name), f"missing public symbol {name!r}"
        assert set(_assertions.__all__) >= {
            "AssertionAdapter",
            "AssertionOperator",
            "PollingDisallowedError",
            "ValidateOperatorDisallowed",
            "assert_value",
            "coerce_operator",
        }


# ---------------------------------------------------------------------------
# Proof that `verify_assertion` is the underlying delegate (defends against a
# future refactor that swaps in a hand-rolled comparison and silently drops
# AssertionEngine's formatter / message customisation).
# ---------------------------------------------------------------------------


def test_assert_value_delegates_to_verify_assertion() -> None:
    sentinel: MagicMock = MagicMock(return_value="sentinel")
    with patch("AgentGuard._assertions.adapter._verify_assertion", sentinel):
        result = assert_value(5, ">=", 3, message="custom-msg")
    assert result == "sentinel"
    sentinel.assert_called_once()
    args, _ = sentinel.call_args
    assert args[0] == 5
    # ``>=`` is a distinct enum member in AssertionEngine 4.x.
    assert args[1] is AssertionOperator[">="]
