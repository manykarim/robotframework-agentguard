"""#42796 metric pack — operator-driven Get keywords (mixin for CodingAgentKeywords).

Per ADR-022 / `docs/proposals/keyword-reduction-table.md` §2.9.a, the 12 Get/
Should pairs collapsed into 12 operator-driven Get keywords. Each keyword
returns the metric value and, when ``assertion_operator`` is supplied, asserts
in-place via :func:`AgentGuard._assertions.assert_value` (delegating to
``robotframework-assertion-engine``'s ``verify_assertion``).

Calling shape::

    Read Edit Ratio    ${session}    >=    4.0
    Stop Hook Violation Count    ${session}    ==    0
    Token Usage Per Prompt    ${session}    <=    100000

The mixin keeps the per-file budget well under 300 lines while leaving the
shared driver / parser / aggregate keywords in :mod:`library`.

Default thresholds from ADR-010 §"Decision" / research §3.3 are no longer
hard-coded; users supply ``assertion_expected`` (the value to compare
against) when they want assertion semantics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from robot.api.deco import keyword

from AgentGuard._assertions import AssertionOperator, assert_value

if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.coding_agent.session.types import Session


def _coerce_numeric(expected: Any) -> Any:
    """Coerce string ``assertion_expected`` to ``float`` for numeric metrics.

    Robot Framework passes positional arguments as strings; AssertionEngine's
    ``verify_assertion`` does not auto-coerce expected values for arithmetic
    operators. Every #42796 metric returns a float, so we coerce the expected
    value to float when it arrives as a string. Non-numeric strings and other
    types pass through unchanged (e.g. for ``validate`` expressions).
    """
    if isinstance(expected, str):
        try:
            return float(expected)
        except ValueError:
            return expected
    return expected


class _MetricKeywordsMixin:
    """All 12 #42796 metric Get keywords (operator-driven). See module docstring."""

    # The helpers below are injected by ``library.py`` (same module) so we do
    # not create an import cycle. Type stubs only:
    if TYPE_CHECKING:  # pragma: no cover

        @staticmethod
        def _value(session: Session, key: str) -> float: ...

        def load_behavioral_report(self, source: Any) -> Any: ...

    # ---- Read / Edit discipline (2 keywords) ----------------------------
    @keyword(name="Read Edit Ratio")
    def read_edit_ratio(
        self,
        session: Session,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Return the read:edit ratio. With ``assertion_operator``/``expected``
        also asserts (typical: ``>= 4.0``)."""
        value = self._value(session, "read_edit_ratio")
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    @keyword(name="Edits Without Prior Read Percent")
    def edits_without_prior_read_percent(
        self,
        session: Session,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Return %% of edits with no prior read. Typical assertion: ``<= 10.0``."""
        value = self._value(session, "edits_without_prior_read")
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    # ---- Loops / interrupts (2 keywords) --------------------------------
    @keyword(name="Reasoning Loops Per 1K Tool Calls")
    def reasoning_loops_per_1k_tool_calls(
        self,
        session: Session,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Return reasoning loops per 1K tool calls. Typical assertion: ``<= 12.0``."""
        value = self._value(session, "reasoning_loops_per_1k")
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    @keyword(name="User Interrupts Per 1K Tool Calls")
    def user_interrupts_per_1k_tool_calls(
        self,
        session: Session,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Return user interrupts per 1K tool calls. Typical assertion: ``<= 2.0``."""
        value = self._value(session, "user_interrupts_per_1k")
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    # ---- Stop hook + tests (2 keywords) ---------------------------------
    @keyword(name="Stop Hook Violation Count")
    def stop_hook_violation_count(
        self,
        session: Session,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Return stop-hook violation count. Typical assertion: ``== 0``."""
        value = self._value(session, "stop_hook_violations")
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    @keyword(name="First Run Test Pass Rate")
    def first_run_test_pass_rate(
        self,
        session: Session,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Return first-run test pass rate. Typical assertion: ``>= 0.9``."""
        value = self._value(session, "first_run_test_pass_rate")
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    # ---- Token / errors (2 keywords) ------------------------------------
    @keyword(name="Token Usage Per Prompt")
    def token_usage_per_prompt(
        self,
        session: Session,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
        baseline: str | None = None,
        multiplier: float = 1.5,
    ) -> float:
        """Return token usage per user prompt.

        Two assertion modes are supported:

        - **Operator mode** — supply ``assertion_operator`` + ``assertion_expected``
          (canonical RF-ecosystem idiom): ``Token Usage Per Prompt ${s} <= 100000``.
        - **Baseline mode** — supply ``baseline=`` (path to a saved
          ``BehavioralReport``) and optional ``multiplier=`` (default ``1.5``);
          asserts ``value <= baseline.token_usage_per_prompt * multiplier``.

        If both modes are supplied, ``baseline=`` wins and the operator pair
        is ignored (documented carve-out for the only metric where the
        threshold is naturally relative to a previous run).
        """
        value = self._value(session, "token_usage_per_prompt")
        if baseline is not None:
            base_report = self.load_behavioral_report(baseline)
            base_metrics = getattr(base_report, "metrics", base_report)
            entry = base_metrics["token_usage_per_prompt"]
            base_val = float(getattr(entry, "value", entry))
            threshold = base_val * float(multiplier)
            return float(assert_value(value, "<=", threshold, message=message))
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    @keyword(name="Self Admitted Errors Per 1K")
    def self_admitted_errors_per_1k(
        self,
        session: Session,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Return self-admitted errors per 1K tool calls. Typical assertion: ``<= 0.2``."""
        value = self._value(session, "self_admitted_errors_per_1k")
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    # ---- Write / repeat / simplest (3 keywords) -------------------------
    @keyword(name="Write Mutation Ratio")
    def write_mutation_ratio(
        self,
        session: Session,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Return write/mutation ratio. Typical assertion: ``<= 0.06``."""
        value = self._value(session, "write_mutation_ratio")
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    @keyword(name="Repeated Edits Per File Count")
    def repeated_edits_per_file_count(
        self,
        session: Session,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Return repeated edits per file. Typical assertion: ``<= 3``."""
        value = self._value(session, "repeated_edits_per_file")
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    @keyword(name="Simplest Word Frequency Per 1K")
    def simplest_word_frequency_per_1k(
        self,
        session: Session,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Return simplest-word frequency per 1K. Typical assertion: ``<= 5``."""
        value = self._value(session, "simplest_word_per_1k")
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))

    # ---- Conventions (1 keyword) ---------------------------------------
    @keyword(name="Convention Violation Rate For Session")
    def convention_violation_rate_for_session(
        self,
        session: Session,
        assertion_operator: AssertionOperator | None = None,
        assertion_expected: Any = None,
        message: str | None = None,
    ) -> float:
        """Return convention-violation rate. Typical assertion: ``<= 0.05``."""
        value = self._value(session, "convention_violation_rate")
        return float(assert_value(value, assertion_operator, _coerce_numeric(assertion_expected), message=message))


__all__ = ["_MetricKeywordsMixin"]
