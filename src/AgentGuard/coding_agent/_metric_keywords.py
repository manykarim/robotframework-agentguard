"""#42796 metric pack — Get + Should keyword pairs (mixin for CodingAgentKeywords).

Split out of :mod:`AgentGuard.coding_agent.library` to keep that file under
300 lines. The mixin contributes 24 keywords (12 metrics × Get/Should). All
work is delegated to :mod:`AgentGuard.coding_agent.metrics.registry` via the
``_metric_value`` / ``_assert_threshold`` helpers re-exported here.

Default thresholds come from ADR-010 §"Decision" / research §3.3 and may be
overridden per-call. Each pair name matches the spec verbatim so the surface
is stable for downstream Robot suites.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from robot.api.deco import keyword

if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.coding_agent.session.types import Session


class _MetricKeywordsMixin:
    """All 24 #42796 metric Get + Should keywords. See module docstring."""

    # The helpers below are injected by ``library.py`` (same module) so we do
    # not create an import cycle. Type stubs only:
    if TYPE_CHECKING:  # pragma: no cover
        @staticmethod
        def _value(session: Session, key: str) -> float: ...

        @staticmethod
        def _assert(*, metric: str, value: float, threshold: float, direction: str) -> float: ...

        def load_behavioral_report(self, source: Any) -> Any: ...

    # ---- Read / Edit discipline (4 keywords) ----------------------------
    @keyword(name="Read Edit Ratio")
    def read_edit_ratio(self, session: Session) -> float:
        return self._value(session, "read_edit_ratio")

    @keyword(name="Read Edit Ratio Should Be Above")
    def read_edit_ratio_should_be_above(self, session: Session, threshold: float = 4.0) -> float:
        v = self.read_edit_ratio(session)
        return self._assert(metric="read_edit_ratio", value=v, threshold=float(threshold), direction="above")

    @keyword(name="Edits Without Prior Read Percent")
    def edits_without_prior_read_percent(self, session: Session) -> float:
        return self._value(session, "edits_without_prior_read")

    @keyword(name="Edits Without Prior Read Percent Should Be Below")
    def edits_without_prior_read_percent_should_be_below(self, session: Session, threshold: float = 10.0) -> float:
        v = self.edits_without_prior_read_percent(session)
        return self._assert(metric="edits_without_prior_read", value=v, threshold=float(threshold), direction="below")

    # ---- Loops / interrupts (4 keywords) --------------------------------
    @keyword(name="Reasoning Loops Per 1K Tool Calls")
    def reasoning_loops_per_1k_tool_calls(self, session: Session) -> float:
        return self._value(session, "reasoning_loops_per_1k")

    @keyword(name="Reasoning Loops Per 1K Tool Calls Should Be Below")
    def reasoning_loops_per_1k_tool_calls_should_be_below(self, session: Session, threshold: float = 12.0) -> float:
        v = self.reasoning_loops_per_1k_tool_calls(session)
        return self._assert(metric="reasoning_loops_per_1k", value=v, threshold=float(threshold), direction="below")

    @keyword(name="User Interrupts Per 1K Tool Calls")
    def user_interrupts_per_1k_tool_calls(self, session: Session) -> float:
        return self._value(session, "user_interrupts_per_1k")

    @keyword(name="User Interrupts Per 1K Should Be Below")
    def user_interrupts_per_1k_should_be_below(self, session: Session, threshold: float = 2.0) -> float:
        v = self.user_interrupts_per_1k_tool_calls(session)
        return self._assert(metric="user_interrupts_per_1k", value=v, threshold=float(threshold), direction="below")

    # ---- Stop hook + tests (4 keywords) ---------------------------------
    @keyword(name="Stop Hook Violation Count")
    def stop_hook_violation_count(self, session: Session) -> float:
        return self._value(session, "stop_hook_violations")

    @keyword(name="Stop Hook Violations Should Be Zero")
    def stop_hook_violations_should_be_zero(self, session: Session) -> float:
        v = self.stop_hook_violation_count(session)
        return self._assert(metric="stop_hook_violations", value=v, threshold=0.0, direction="zero")

    @keyword(name="First Run Test Pass Rate")
    def first_run_test_pass_rate(self, session: Session) -> float:
        return self._value(session, "first_run_test_pass_rate")

    @keyword(name="First Run Test Pass Rate Should Be Above")
    def first_run_test_pass_rate_should_be_above(self, session: Session, threshold: float = 0.9) -> float:
        v = self.first_run_test_pass_rate(session)
        return self._assert(metric="first_run_test_pass_rate", value=v, threshold=float(threshold), direction="above")

    # ---- Token / errors (4 keywords) ------------------------------------
    @keyword(name="Token Usage Per Prompt")
    def token_usage_per_prompt(self, session: Session) -> float:
        return self._value(session, "token_usage_per_prompt")

    @keyword(name="Token Usage Per Prompt Should Be Below")
    def token_usage_per_prompt_should_be_below(
        self,
        session: Session,
        threshold: float | None = None,
        baseline: str | None = None,
        multiplier: float = 1.5,
    ) -> float:
        """Threshold defaults to ``baseline.token_usage_per_prompt × multiplier``
        when ``baseline`` (path to a saved BehavioralReport) is given."""
        from AgentGuard.coding_agent.exceptions import DriverDispatchError

        value = self.token_usage_per_prompt(session)
        if threshold is None:
            if not baseline:
                raise DriverDispatchError("provide threshold= or baseline=")
            base_report = self.load_behavioral_report(baseline)
            base_metrics = getattr(base_report, "metrics", base_report)
            entry = base_metrics["token_usage_per_prompt"]
            base_val = float(getattr(entry, "value", entry))
            threshold = base_val * float(multiplier)
        return self._assert(
            metric="token_usage_per_prompt",
            value=value,
            threshold=float(threshold),
            direction="below",
        )

    @keyword(name="Self Admitted Errors Per 1K")
    def self_admitted_errors_per_1k(self, session: Session) -> float:
        return self._value(session, "self_admitted_errors_per_1k")

    @keyword(name="Self Admitted Errors Per 1K Should Be Below")
    def self_admitted_errors_per_1k_should_be_below(self, session: Session, threshold: float = 0.2) -> float:
        v = self.self_admitted_errors_per_1k(session)
        return self._assert(metric="self_admitted_errors_per_1k", value=v, threshold=float(threshold), direction="below")

    # ---- Write / repeat / simplest (6 keywords) -------------------------
    @keyword(name="Write Mutation Ratio")
    def write_mutation_ratio(self, session: Session) -> float:
        return self._value(session, "write_mutation_ratio")

    @keyword(name="Write Mutation Ratio Should Be Below")
    def write_mutation_ratio_should_be_below(self, session: Session, threshold: float = 0.06) -> float:
        v = self.write_mutation_ratio(session)
        return self._assert(metric="write_mutation_ratio", value=v, threshold=float(threshold), direction="below")

    @keyword(name="Repeated Edits Per File Count")
    def repeated_edits_per_file_count(self, session: Session) -> float:
        return self._value(session, "repeated_edits_per_file")

    @keyword(name="Repeated Edits Per File Should Be Below")
    def repeated_edits_per_file_should_be_below(self, session: Session, threshold: float = 3.0) -> float:
        v = self.repeated_edits_per_file_count(session)
        return self._assert(metric="repeated_edits_per_file", value=v, threshold=float(threshold), direction="below")

    @keyword(name="Simplest Word Frequency Per 1K")
    def simplest_word_frequency_per_1k(self, session: Session) -> float:
        return self._value(session, "simplest_word_per_1k")

    @keyword(name="Simplest Word Frequency Per 1K Should Be Below")
    def simplest_word_frequency_per_1k_should_be_below(self, session: Session, threshold: float = 5.0) -> float:
        v = self.simplest_word_frequency_per_1k(session)
        return self._assert(metric="simplest_word_per_1k", value=v, threshold=float(threshold), direction="below")

    # ---- Conventions (2 keywords) ---------------------------------------
    @keyword(name="Convention Violation Rate For Session")
    def convention_violation_rate_for_session(self, session: Session) -> float:
        return self._value(session, "convention_violation_rate")

    @keyword(name="Convention Violation Rate For Session Should Be Below")
    def convention_violation_rate_for_session_should_be_below(self, session: Session, threshold: float = 0.05) -> float:
        v = self.convention_violation_rate_for_session(session)
        return self._assert(metric="convention_violation_rate", value=v, threshold=float(threshold), direction="below")


__all__ = ["_MetricKeywordsMixin"]
