"""AgentGuard assertion shared-kernel — wraps `robotframework-assertion-engine`.

Per ADR-022 (single-phase full replacement): every Get-style keyword that
previously had a Should-pair sibling now accepts ``(assertion_operator,
assertion_expected, message)`` parameters. When ``assertion_operator is None``
the keyword returns the value unchanged. When supplied, it asserts in-place
via :func:`AssertionAdapter.verify` and returns the value.

The adapter enforces two ACL rules at the AssertionEngine boundary
(`docs/ddd/assertion-engine-shared-kernel.md` §4):

- **Polling AVOIDANCE for Tier-2/3 keywords** (ADR-019). Polling LLM-backed
  keywords compounds spend; the adapter raises :class:`PollingDisallowedError`
  if the consuming keyword is marked Tier-2 or Tier-3 and the user passes a
  ``polling=`` argument.
- **`validate` operator SANDBOXING** (ADR-013). The ``validate`` operator
  evaluates a Python expression (`BuiltIn().evaluate()`); disabled by default,
  raises :class:`ValidateOperatorDisallowed` unless explicitly enabled.

Public re-exports kept tight so `library.py` modules just do
``from AgentGuard._assertions import assert_value, AssertionOperator``.
"""

from AgentGuard._assertions.adapter import (
    AssertionAdapter,
    AssertionOperator,
    PollingDisallowedError,
    ValidateOperatorDisallowed,
    assert_value,
    coerce_operator,
)

__all__ = [
    "AssertionAdapter",
    "AssertionOperator",
    "PollingDisallowedError",
    "ValidateOperatorDisallowed",
    "assert_value",
    "coerce_operator",
]
