"""MCPScenarioKeywords — Robot Framework keyword surface for ADR-021.

Two equally first-class usage patterns:

1. **YAML-driven (rf-mcp drop-in)**::

       ${scenario}=    Load MCP Scenario    scenarios/restful_booker_api.yaml
       ${result}=    Run MCP Scenario    ${scenario}    server=${HANDLE}
       Tool Hit Rate Should Be Above    ${result}    0.7

2. **Pure Robot Framework (no YAML required)**::

       ${scenario}=    Create Scenario    id=demo    prompt=Use add(2,3)    expected_outcome=adds 2+3=5
       Add Expected Tool    ${scenario}    add    min_calls=1    max_calls=1
       ${session}=    Start Tracked MCP Session    ${HANDLE}
       Call Tracked Tool    ${session}    add    {"x": 2, "y": 3}
       ${result}=    Compute Scenario Result    ${scenario}    ${session}
       Tool Hit Rate Should Be Above    ${result}    0.99
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from robot.api.deco import keyword

from AgentGuard.mcp_scenario import (
    artifacts,
    loader,
    runner,
    statistics,
)
from AgentGuard.mcp_scenario.tracker import TrackedMCPSession
from AgentGuard.mcp_scenario.types import (
    ExpectedToolCall,
    Scenario,
    ScenarioResult,
    ToolCallRecord,
    ToolCallStatistics,
)

if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.mcp.server_handle import ServerHandle


class MCPScenarioKeywords:
    """Test-harness keywords for MCP servers, Agent Skills, and coding agents.

    Composed into the top-level :class:`AgentGuard.AgentGuard` library.
    """

    ROBOT_LIBRARY_SCOPE = "SUITE"

    def __init__(self, provider: Any | None = None) -> None:
        # ``provider`` accepted for DynamicCore composition contract; not used
        # directly here — the runner reaches for the LocalDriver which has its
        # own provider plumbing.
        self._provider = provider

    # ================================================================
    # Lifecycle: load / save / build
    # ================================================================

    @keyword(name="Load MCP Scenario")
    def load_mcp_scenario(self, path: str | Path) -> Scenario:
        """Parse a Scenario YAML file (rf-mcp v1 schema)."""
        return loader.load_scenario(path)

    @keyword(name="Save MCP Scenario")
    def save_mcp_scenario(self, scenario: Scenario, path: str | Path) -> Path:
        """Round-trip a Scenario back to YAML."""
        return loader.save_scenario(scenario, path)

    @keyword(name="Create Scenario")
    def create_scenario(
        self,
        id: str,
        prompt: str,
        expected_outcome: str,
        name: str | None = None,
        description: str = "",
        context: str = "generic",
        min_tool_hit_rate: float = 0.8,
        tags: list[str] | None = None,
    ) -> Scenario:
        """Build a Scenario inline — no YAML required.

        Append ``ExpectedToolCall``s afterwards via ``Add Expected Tool``.
        """
        return loader.scenario_from_dict(
            {
                "id": id,
                "name": name or id,
                "description": description,
                "prompt": prompt,
                "expected_outcome": expected_outcome,
                "context": context,
                "min_tool_hit_rate": float(min_tool_hit_rate),
                "tags": list(tags or []),
            }
        )

    @keyword(name="Add Expected Tool")
    def add_expected_tool(
        self,
        scenario: Scenario,
        tool_name: str,
        min_calls: int = 1,
        max_calls: int | None = None,
        required_params: dict[str, Any] | None = None,
    ) -> Scenario:
        """Append an :class:`ExpectedToolCall` to ``scenario.expected_tools``."""
        scenario.expected_tools.append(
            ExpectedToolCall(
                tool_name=tool_name,
                min_calls=int(min_calls),
                max_calls=(int(max_calls) if max_calls is not None else None),
                required_params=(dict(required_params) if required_params else None),
            )
        )
        return scenario

    # ================================================================
    # Tracked session
    # ================================================================

    @keyword(name="Start Tracked MCP Session")
    def start_tracked_mcp_session(self, handle: Any) -> TrackedMCPSession:
        """Wrap an MCP :class:`ServerHandle` so every ``Call Tracked Tool`` records."""
        from AgentGuard.mcp.library import MCPKeywords

        mcp = MCPKeywords()
        return TrackedMCPSession(handle=handle, mcp=mcp)

    @keyword(name="Call Tracked Tool")
    def call_tracked_tool(
        self,
        session: TrackedMCPSession,
        name: str,
        arguments: dict[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        """Dispatch ``name(arguments)`` through ``session`` and record the call."""
        return session.call_tool(name, arguments)

    @keyword(name="Get Tool Call Records")
    def get_tool_call_records(self, session: TrackedMCPSession) -> list[ToolCallRecord]:
        """Return the in-memory record list (read-only snapshot semantics)."""
        return list(session.records)

    @keyword(name="Reset Tracked MCP Session")
    def reset_tracked_mcp_session(self, session: TrackedMCPSession) -> None:
        """Clear records — handy to scope hit rate to one suite phase."""
        session.reset()

    @keyword(name="End Tracked MCP Session")
    def end_tracked_mcp_session(self, session: TrackedMCPSession) -> None:
        """Mark the session ended; records stay readable."""
        session.end()

    # ================================================================
    # Run a scenario (manual / local driver)
    # ================================================================

    @keyword(name="Run MCP Scenario")
    def run_mcp_scenario(
        self,
        scenario: Scenario,
        server: ServerHandle | None = None,
        session: TrackedMCPSession | None = None,
        driver: str = "manual",
        model: str | None = None,
        max_turns: int = 12,
        metadata: dict[str, Any] | None = None,
    ) -> ScenarioResult:
        """Drive ``scenario`` and return a :class:`ScenarioResult`.

        ``driver`` ∈ ``{manual, local}``. ``manual`` requires ``session`` to
        have been pre-populated by the caller. ``local`` uses the OpenRouter-
        backed LocalDriver and requires ``server``.
        """
        if driver == "manual":
            if session is None:
                raise ValueError("driver=manual requires session= (use Start Tracked MCP Session first)")
            return runner.run_manual_scenario(scenario, session)
        if driver == "local":
            if server is None and session is None:
                raise ValueError("driver=local requires either server= or session=")
            if session is None:
                session = self.start_tracked_mcp_session(server)
            return runner.run_local_scenario(
                scenario,
                session,
                model=model,
                max_turns=max_turns,
                extra_metadata=metadata,
            )
        raise ValueError(f"unknown driver {driver!r}; expected 'manual' or 'local'")

    @keyword(name="Compute Scenario Result")
    def compute_scenario_result(
        self,
        scenario: Scenario,
        session: TrackedMCPSession,
    ) -> ScenarioResult:
        """Aggregate ``session.records`` against ``scenario.expected_tools``.

        Convenience wrapper around ``Run MCP Scenario  driver=manual``.
        """
        return runner.run_manual_scenario(scenario, session)

    # ================================================================
    # Result IO
    # ================================================================

    @keyword(name="Save Scenario Result")
    def save_scenario_result(self, result: ScenarioResult, path: str | Path) -> Path:
        """Persist ``result`` as JSON (rf-mcp metrics/*.json shape)."""
        return loader.save_scenario_result(result, path)

    @keyword(name="Load Scenario Result")
    def load_scenario_result(self, path: str | Path) -> ScenarioResult:
        """Read a previously-saved :class:`ScenarioResult` JSON."""
        return loader.load_scenario_result(path)

    # ================================================================
    # Aggregate assertions
    # ================================================================

    @keyword(name="Tool Hit Rate")
    def tool_hit_rate(
        self,
        target: ScenarioResult | TrackedMCPSession,
        scenario: Scenario | None = None,
    ) -> float:
        """Return the hit rate from a result or compute it from a session+scenario."""
        if isinstance(target, ScenarioResult):
            return target.tool_hit_rate
        if scenario is None:
            raise ValueError("hit rate from a session needs scenario=")
        return statistics.calculate_tool_hit_rate(target.records, scenario.expected_tools)

    @keyword(name="Tool Hit Rate Should Be Above")
    def tool_hit_rate_should_be_above(
        self,
        target: ScenarioResult | TrackedMCPSession,
        threshold: float,
        scenario: Scenario | None = None,
    ) -> float:
        """Assert hit rate ≥ ``threshold``."""
        rate = self.tool_hit_rate(target, scenario=scenario)
        if rate < float(threshold):
            raise AssertionError(f"Tool hit rate {rate:.3f} < threshold {float(threshold):.3f}")
        return float(rate)

    @keyword(name="Tool Call Success Rate")
    def tool_call_success_rate(self, target: ScenarioResult | TrackedMCPSession) -> float:
        """Successful / total over the recorded calls."""
        records = self._records_of(target)
        return float(statistics.summary_stats(records).success_rate)

    @keyword(name="Tool Call Success Rate Should Be Above")
    def tool_call_success_rate_should_be_above(
        self,
        target: ScenarioResult | TrackedMCPSession,
        threshold: float,
    ) -> float:
        rate = self.tool_call_success_rate(target)
        if rate < float(threshold):
            raise AssertionError(f"Tool call success rate {rate:.3f} < threshold {float(threshold):.3f}")
        return float(rate)

    @keyword(name="Tool Call Count")
    def tool_call_count(
        self,
        target: ScenarioResult | TrackedMCPSession,
        name: str | None = None,
    ) -> int:
        """Total recorded calls, or per-tool count when ``name=`` is given."""
        records = self._records_of(target)
        if name is None:
            return int(len(records))
        return int(sum(1 for r in records if r.tool_name == name))

    @keyword(name="Tool Call Count Should Be Between")
    def tool_call_count_should_be_between(
        self,
        target: ScenarioResult | TrackedMCPSession,
        min_count: int,
        max_count: int | None = None,
        name: str | None = None,
    ) -> int:
        count = self.tool_call_count(target, name=name)
        lo = int(min_count)
        if count < lo:
            raise AssertionError(f"Tool call count {count} < min {lo} (filter name={name!r})")
        if max_count is not None and count > int(max_count):
            raise AssertionError(f"Tool call count {count} > max {int(max_count)} (filter name={name!r})")
        return int(count)

    @keyword(name="Failed Tool Call Count Should Be At Most")
    def failed_tool_call_count_should_be_at_most(
        self,
        target: ScenarioResult | TrackedMCPSession,
        max_failures: int,
    ) -> int:
        records = self._records_of(target)
        failed = sum(1 for r in records if not r.success)
        if failed > int(max_failures):
            failures = [r.tool_name for r in records if not r.success]
            raise AssertionError(f"Failed tool call count {failed} > max {int(max_failures)} ({failures})")
        return failed

    @keyword(name="Required Tool Should Have Been Called With Params")
    def required_tool_should_have_been_called_with_params(
        self,
        target: ScenarioResult | TrackedMCPSession,
        tool_name: str,
        required_params: dict[str, Any],
    ) -> None:
        """Assert every recorded call to ``tool_name`` carried ``required_params``."""
        records = self._records_of(target)
        expected = ExpectedToolCall(tool_name=tool_name, required_params=dict(required_params))
        if not statistics.required_params_match(records, expected):
            actuals = [r.arguments for r in records if r.tool_name == tool_name]
            raise AssertionError(
                f"required_params {required_params} not satisfied for {tool_name!r}. Actual arguments seen: {actuals}"
            )

    @keyword(name="Scenario Result Should Be Successful")
    def scenario_result_should_be_successful(self, result: ScenarioResult) -> None:
        """Assert ``result.success`` is True."""
        if not result.success:
            raise AssertionError(
                f"Scenario {result.scenario_id!r} failed: hit_rate={result.tool_hit_rate:.3f}, "
                f"errors={result.errors[:3]}"
            )

    @keyword(name="Tool Call Statistics")
    def tool_call_statistics(
        self,
        target: ScenarioResult | TrackedMCPSession,
    ) -> ToolCallStatistics:
        """Return the rf-mcp-shaped summary stats."""
        return statistics.summary_stats(self._records_of(target))

    # ================================================================
    # Artifact analysis
    # ================================================================

    @keyword(name="Get Generated Robot Suite Path")
    def get_generated_robot_suite_path(self, result: ScenarioResult) -> Path | None:
        """Return the first agent-emitted Robot suite path (or None)."""
        suites = artifacts.get_generated_robot_suites(result)
        return suites[0] if suites else None

    @keyword(name="Get Generated Robot Suites")
    def get_generated_robot_suites(self, result: ScenarioResult) -> list[Path]:
        """Return all agent-emitted Robot suite paths."""
        return artifacts.get_generated_robot_suites(result)

    @keyword(name="Generated Robot Suite Should Pass")
    def generated_robot_suite_should_pass(
        self,
        suite_path: str | Path,
        timeout_seconds: int = 60,
    ) -> None:
        """``robot --dryrun`` the suite; raise if exit code is non-zero."""
        exit_code, stdout, stderr = artifacts.robot_dryrun(Path(suite_path), timeout_seconds=timeout_seconds)
        if exit_code != 0:
            raise AssertionError(
                f"Generated Robot suite {suite_path} failed dryrun (exit {exit_code}). "
                f"stdout[:200]={stdout[:200]!r}, stderr[:200]={stderr[:200]!r}"
            )

    @keyword(name="Get Generated Files")
    def get_generated_files(self, result: ScenarioResult) -> list[Path]:
        """Return arbitrary files the agent produced under cwd."""
        return artifacts.get_generated_files(result)

    @keyword(name="Generated Artifact Should Match Schema")
    def generated_artifact_should_match_schema(
        self,
        payload: dict[str, Any] | list[Any],
        schema: dict[str, Any],
    ) -> None:
        """JSON-Schema validate ``payload``."""
        artifacts.validate_json_artifact(payload, schema)

    # ================================================================
    # Statistical comparison (delegates to AgentGuard.stats)
    # ================================================================

    @keyword(name="Compare Scenarios Pass Rate")
    def compare_scenarios_pass_rate(
        self,
        results: list[ScenarioResult],
        threshold: float = 0.5,
        k: int = 1,
    ) -> float:
        """``pass@k`` over the success flags of ``results`` (delegates to Stats)."""
        from AgentGuard.stats.pass_at_k import pass_at_k

        outcomes = [bool(r.success) for r in results]
        return pass_at_k(outcomes, k=int(k))

    @keyword(name="Tool Hit Rate Distribution Should Stochastically Dominate")
    def tool_hit_rate_distribution_should_stochastically_dominate(
        self,
        current: list[ScenarioResult],
        baseline: list[ScenarioResult],
        alpha: float = 0.05,
    ) -> tuple[float, float]:
        """Mann-Whitney U over hit-rate distributions; raise if p ≥ alpha."""
        from AgentGuard.stats.mannwhitney import mann_whitney_u

        cur = [r.tool_hit_rate for r in current]
        base = [r.tool_hit_rate for r in baseline]
        outcome = mann_whitney_u(cur, base, alternative="greater")
        u = float(outcome.statistic)
        p = float(outcome.pvalue)
        if p >= float(alpha):
            raise AssertionError(
                f"Mann-Whitney U: hit rate did not stochastically dominate baseline "
                f"(U={u:.2f}, p={p:.4f} ≥ alpha={alpha})"
            )
        return u, p

    @keyword(name="Scenario Drift Should Not Exceed")
    def scenario_drift_should_not_exceed(
        self,
        current: list[ScenarioResult],
        baseline: list[ScenarioResult],
        max_delta: float = 0.3,
    ) -> float:
        """Cliff's δ on ``total_tool_calls`` distributions; raise on excessive drift."""
        from AgentGuard.stats.cliffs_delta import cliffs_delta

        cur = [float(r.total_tool_calls) for r in current]
        base = [float(r.total_tool_calls) for r in baseline]
        delta = cliffs_delta(cur, base)
        if abs(delta) > float(max_delta):
            raise AssertionError(f"Cliff's δ on total_tool_calls = {delta:.3f}, exceeds max {max_delta}")
        return delta

    # ================================================================
    # Helpers
    # ================================================================

    @staticmethod
    def _records_of(target: ScenarioResult | TrackedMCPSession) -> list[ToolCallRecord]:
        if isinstance(target, ScenarioResult):
            return list(target.tool_calls)
        return list(target.records)


__all__ = ["MCPScenarioKeywords"]
