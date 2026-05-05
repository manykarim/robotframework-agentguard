"""AssertionAdapter — the single point at which AgentGuard sub-libraries call
into ``assertionengine.verify_assertion``.

Per ADR-022 §"Phase 4-D — One-Shot Replacement", every Get-style keyword in
AgentGuard now follows this shape::

    @keyword(name="Read Edit Ratio")
    def read_edit_ratio(
        self,
        session: Session,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        value = float(self._compute_ratio(session))
        return assert_value(
            value, assertion_operator, assertion_expected, message=message
        )

The :func:`assert_value` helper is the canonical one-call entry point; pass-
through ``assertion_operator=None`` returns the value unchanged. With an
operator, AssertionEngine performs the comparison and raises ``AssertionError``
(re-raised as RF test failure) if it fails.

Both ACL rules from `docs/ddd/assertion-engine-shared-kernel.md` §4 are
enforced here; see the module docstring of :mod:`AgentGuard._assertions`.
"""

from __future__ import annotations

from typing import Any

from assertionengine import AssertionOperator
from assertionengine import verify_assertion as _verify_assertion


class AssertionError_(AssertionError):  # noqa: N801 — trailing _ disambiguates from builtin
    """Marker so library code can distinguish adapter-raised failures."""


class PollingDisallowedError(RuntimeError):
    """Raised when a Tier-2/3 keyword is given a ``polling=`` argument.

    Re-sampling LLM-backed assertions compounds cost. Use Statistics' explicit
    ``Run N Times`` / ``Pass At K Should Be Above`` instead.
    """


class ValidateOperatorDisallowed(RuntimeError):
    """Raised when ``validate`` is invoked without ``allow_validate=True``.

    AssertionEngine's ``validate`` op evaluates user-supplied Python via
    ``BuiltIn().evaluate()`` (effectively ``eval()``). Per ADR-013 sandbox
    policy, default is **disabled**.
    """


def coerce_operator(value: AssertionOperator | str | None) -> AssertionOperator | None:
    """Accept enum, alias string, or None; return enum or None."""
    if value is None:
        return None
    if isinstance(value, AssertionOperator):
        return value
    try:
        return AssertionOperator[value]
    except KeyError as exc:
        valid = sorted({member.name for member in AssertionOperator})
        raise ValueError(f"Unknown assertion operator {value!r}. Valid: {valid}") from exc


def assert_value(
    value: Any,
    assertion_operator: AssertionOperator | str | None = None,
    assertion_expected: Any = None,
    *,
    message: str | None = None,
    custom_message: str | None = None,
    tier: int = 1,
    polling: float | None = None,
    allow_validate: bool = False,
) -> Any:
    """Apply ``verify_assertion`` with AgentGuard's policy gates.

    - ``assertion_operator is None`` → returns ``value`` unchanged (no assertion).
    - Otherwise → calls ``verify_assertion(value, op, expected, message, custom_message)``
      and returns its result. AssertionEngine's ``then``/``evaluate`` operator
      returns the eval'd Python expression rather than ``value``.
    - ``tier >= 2`` and ``polling is not None`` → raises ``PollingDisallowedError``.
    - ``operator == validate`` and ``allow_validate is False`` → raises
      ``ValidateOperatorDisallowed``.

    The helper is a free function (not method-on-adapter) because every
    sub-library calls it identically; an adapter *instance* exists only for
    contexts with non-default ``allow_validate`` / ``polling`` configuration
    (currently none).
    """
    op = coerce_operator(assertion_operator)
    if op is None:
        return value

    if polling is not None and tier >= 2:
        raise PollingDisallowedError(
            f"polling is disallowed for Tier-{tier} keywords (ADR-019). "
            "Use Stats.Run N Times + Pass At K Should Be Above for re-sampling."
        )

    if op is AssertionOperator.validate and not allow_validate:
        raise ValidateOperatorDisallowed(
            "the `validate` operator is disabled by default (ADR-013). "
            "Enable per-suite via `Configure Assertion Engine validate_enabled=True` "
            "and an explicit non-`process` SandboxBackend."
        )

    return _verify_assertion(
        value,
        op,
        assertion_expected,
        message or "",
        custom_message,
    )


class AssertionAdapter:
    """Stateful adapter for sub-libraries that need per-instance configuration.

    Most call sites use the free :func:`assert_value` instead. Use the class
    when you need to bind a tier or `allow_validate` flag once and reuse
    across many keyword bodies.
    """

    def __init__(
        self,
        *,
        tier: int = 1,
        allow_validate: bool = False,
    ) -> None:
        self.tier = tier
        self.allow_validate = allow_validate

    def verify(
        self,
        value: Any,
        assertion_operator: AssertionOperator | str | None = None,
        assertion_expected: Any = None,
        *,
        message: str | None = None,
        custom_message: str | None = None,
        polling: float | None = None,
    ) -> Any:
        return assert_value(
            value,
            assertion_operator,
            assertion_expected,
            message=message,
            custom_message=custom_message,
            tier=self.tier,
            polling=polling,
            allow_validate=self.allow_validate,
        )


__all__ = [
    "AssertionAdapter",
    "AssertionOperator",
    "PollingDisallowedError",
    "ValidateOperatorDisallowed",
    "assert_value",
    "coerce_operator",
]
