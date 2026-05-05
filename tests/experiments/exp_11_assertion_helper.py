"""Tiny RF library — wraps assertionengine.verify_assertion so the .robot
suite can call it as a single keyword.

In real AgentGuard adoption, the `value` arg will come from the wrapped Get
keyword's typed return (e.g. `Tool Hit Rate` returns `float`, not `str`).
Robot's positional arg coercion would otherwise pass everything as `str` and
break numeric `validate` expressions — exp_11 confirms this is a real RF gotcha
that the proposal must call out.
"""

from __future__ import annotations

from typing import Any

from assertionengine import AssertionOperator, verify_assertion
from robot.api.deco import keyword


@keyword(name="Verify Float")
def verify_float(value: float, operator: str, expected: Any) -> Any:
    """Type-typed wrapper — `value` is coerced to float before verify_assertion.

    This mirrors real Get-style keywords (`Tool Hit Rate`, `Read Edit Ratio`)
    whose return types are declared `-> float` so AssertionEngine sees a real
    Python float, not the RF string positional.
    """
    op = AssertionOperator[operator]
    return verify_assertion(float(value), op, expected)


@keyword(name="Verify Int")
def verify_int(value: int, operator: str, expected: Any) -> Any:
    op = AssertionOperator[operator]
    return verify_assertion(int(value), op, expected)


@keyword(name="Verify Object")
def verify_object(value: Any, operator: str, expected: Any) -> Any:
    """For non-scalar values (lists, dicts) — pass through as-is."""
    op = AssertionOperator[operator]
    return verify_assertion(value, op, expected)


@keyword(name="Verify Untyped")
def verify_untyped(value: Any, operator: str, expected: Any) -> Any:
    """Demonstrates the untyped failure mode — value arrives as `str`."""
    op = AssertionOperator[operator]
    return verify_assertion(value, op, expected)
