"""CodingAgentKeywords — Robot Framework surface for the CodingAgent context.

ADR-009 (drivers) + ADR-010 (Session schema + #42796 metrics). Composed into
the top-level :class:`AgentGuard.library.AgentGuard` via ``DynamicCore``.

Sibling modules (``drivers``, ``session.parser``, ``metrics.pack``) are
imported lazily inside each keyword: if a sibling has not landed yet during
the parallel Phase-3 race, ``library.py`` still imports cleanly and the
affected keyword raises ``RuntimeError("phase3 module not yet wired")``.

The 12 metric Get keywords (operator-driven per ADR-022) live in
:mod:`AgentGuard.coding_agent._metric_keywords` to keep this file under the
300-line per-file budget; we mix them in below.

Total keywords: ~22 (3 driver + 4 parser + 12 metric + 3 aggregate).
"""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from robot.api.deco import keyword, library

from AgentGuard.coding_agent._metric_keywords import _MetricKeywordsMixin
from AgentGuard.coding_agent.exceptions import (
    DriverDispatchError,
    MetricThresholdViolated,
    SessionParseFailed,
    SessionSchemaInvalid,
)

if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.coding_agent.drivers.base import DriverResult
    from AgentGuard.coding_agent.metrics.types import BehavioralReport
    from AgentGuard.coding_agent.session.types import Session
    from AgentGuard.providers.base import LLMProviderAdapter

logger = logging.getLogger("AgentGuard.coding_agent")

_NOT_WIRED = "phase3 module not yet wired"


def _import_drivers() -> Any:
    try:
        from AgentGuard.coding_agent.drivers import base as _base
        from AgentGuard.coding_agent.drivers import registry as _registry
    except ImportError as exc:
        raise RuntimeError(f"{_NOT_WIRED}: drivers ({exc})") from exc
    return _base, _registry


def _import_parser() -> Any:
    try:
        from AgentGuard.coding_agent.session import parser as _parser
        from AgentGuard.coding_agent.session import types as _types
    except ImportError as exc:
        raise RuntimeError(f"{_NOT_WIRED}: session.parser ({exc})") from exc
    return _parser, _types


def _import_metrics() -> Any:
    try:
        from AgentGuard.coding_agent.metrics import pack as _pack
        from AgentGuard.coding_agent.metrics import registry as _registry
        from AgentGuard.coding_agent.metrics import types as _types
    except ImportError as exc:
        raise RuntimeError(f"{_NOT_WIRED}: metrics ({exc})") from exc
    return _pack, _registry, _types


@library(scope="SUITE", auto_keywords=False, version="0.1.0")
class CodingAgentKeywords(_MetricKeywordsMixin):
    """Robot Framework keywords for driving coding-agent CLIs and asserting on
    the resulting Session via the #42796 behavioural metric pack."""

    ROBOT_LIBRARY_SCOPE = "SUITE"

    def __init__(
        self,
        provider: LLMProviderAdapter | None = None,
        default_model: str | None = None,
    ) -> None:
        self._provider = provider
        self._default_model = default_model
        self._last_result: DriverResult | None = None

    # ---- shared helper consumed by the metric mixin --------------------
    @staticmethod
    def _value(session: Session, key: str) -> float:
        """Run a single metric calculator from ``metrics.registry.METRICS``."""
        _, registry_mod, _ = _import_metrics()
        try:
            spec = registry_mod.get_metric(key)
        except KeyError as exc:
            raise DriverDispatchError(str(exc)) from exc
        # ``threshold=None`` keeps the calculator from setting ``passed`` —
        # the keyword layer owns assertions (now via AssertionEngine); the
        # calculator only returns the value.
        result = spec.compute(session, threshold=None)
        return float(getattr(result, "value", result))

    # ---- Driver --------------------------------------------------------
    @keyword(name="Run Coding Agent")
    def run_coding_agent(
        self,
        prompt: str,
        driver: str = "local",
        model: str | None = None,
        cwd: str | None = None,
        max_turns: int = 25,
        timeout_seconds: int = 600,
        capture_jsonl: bool = True,
        jsonl_path: str | None = None,
    ) -> DriverResult:
        """Dispatch to ``drivers.registry.get_driver(driver)`` and return its
        :class:`DriverResult` (with the parsed :class:`Session` attached)."""
        base_mod, registry_mod = _import_drivers()
        config = base_mod.DriverConfig(
            model=model or self._default_model,
            cwd=cwd,
            max_turns=int(max_turns),
            timeout_seconds=int(timeout_seconds),
            capture_jsonl=bool(capture_jsonl),
            jsonl_path=jsonl_path,
        )
        try:
            # ``LocalDriver`` accepts ``provider=``; subprocess drivers don't.
            kwargs = {"provider": self._provider} if driver == "local" else {}
            driver_obj = registry_mod.get_driver(driver, **kwargs)
            result = driver_obj.run(prompt, config)
        except Exception as exc:
            raise DriverDispatchError(f"driver={driver!r} failed: {exc}") from exc
        self._last_result = result
        return result  # type: ignore[no-any-return]

    @keyword(name="Run Coding Agent And Save Session")
    def run_coding_agent_and_save_session(
        self,
        prompt: str,
        driver: str = "local",
        model: str | None = None,
        save_to: str | None = None,
    ) -> DriverResult:
        """Same as :meth:`run_coding_agent`; additionally persists the Session."""
        result = self.run_coding_agent(prompt, driver=driver, model=model)
        if save_to:
            self.save_session_snapshot(getattr(result, "session", result), save_to)
        return result  # type: ignore[no-any-return]

    @keyword(name="Get Last Coding Agent Session")
    def get_last_coding_agent_session(self) -> Session:
        """Return the most recent driver run's Session (suite-scope memory)."""
        if self._last_result is None:
            raise DriverDispatchError("no coding-agent run recorded in this suite")
        sess = getattr(self._last_result, "session", None)
        if sess is None:
            raise DriverDispatchError("last DriverResult had no session attached")
        return sess  # type: ignore[no-any-return]

    # ---- Parser --------------------------------------------------------
    @keyword(name="Parse Session JSONL")
    def parse_session_jsonl(self, path: str, format: str | None = None) -> Session:
        """Parse a coding-agent session log; ``format`` overrides auto-detect."""
        parser_mod, _ = _import_parser()
        try:
            return parser_mod.parse(path, format=format)  # type: ignore[no-any-return]
        except Exception as exc:
            raise SessionParseFailed(f"parse({path!r}) failed: {exc}") from exc

    @keyword(name="Save Session Snapshot")
    def save_session_snapshot(self, session: Session, path: str) -> str:
        """Persist a :class:`Session` as JSON for later diffing / replay."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = dataclasses.asdict(session)
        except TypeError as exc:
            raise SessionParseFailed(f"session not a dataclass: {exc}") from exc
        target.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
        return str(target)

    @keyword(name="Load Session Snapshot")
    def load_session_snapshot(self, path: str) -> Session:
        """Inverse of :meth:`save_session_snapshot` — JSON → Session."""
        _, types_mod = _import_parser()
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            return types_mod.Session(**payload)  # type: ignore[no-any-return]
        except Exception as exc:
            raise SessionParseFailed(f"load({path!r}) failed: {exc}") from exc

    @keyword(name="Validate Session Schema")
    def validate_session_schema(self, session: Session) -> bool:
        """Sanity-check a Session: id present, messages list non-degenerate."""
        if not getattr(session, "id", None):
            raise SessionSchemaInvalid("session.id is empty")
        msgs = getattr(session, "messages", None)
        if msgs is None or not isinstance(msgs, list):
            raise SessionSchemaInvalid("session.messages must be a list")
        return True

    # ---- Aggregate -----------------------------------------------------
    @keyword(name="Compute 42796 Metric Pack")
    def compute_42796_metric_pack(
        self, session: Session, baseline: BehavioralReport | str | None = None
    ) -> BehavioralReport:
        """Run all 12 calculators; return a :class:`BehavioralReport`."""
        pack_mod, _, _ = _import_metrics()
        base = self.load_behavioral_report(baseline) if isinstance(baseline, str) else baseline
        return pack_mod.compute_42796_pack(session, baseline=base)  # type: ignore[no-any-return]

    @keyword(name="Behavioral Report Should Match Baseline")
    def behavioral_report_should_match_baseline(
        self,
        current: BehavioralReport,
        baseline: BehavioralReport | str,
        alpha: float = 0.05,
    ) -> dict[str, float]:
        """Per-metric Mann-Whitney U vs baseline; raise on regression.

        Delegates to :func:`AgentGuard.stats.mannwhitney.mann_whitney_u`. Each
        metric's per-run sample (``MetricResult.samples``) is compared to the
        baseline's; metrics missing samples are skipped with a debug log.
        """
        from AgentGuard.stats.mannwhitney import mann_whitney_u

        base = self.load_behavioral_report(baseline) if isinstance(baseline, str) else baseline
        cur_metrics: Any = getattr(current, "metrics", current)
        base_metrics: Any = getattr(base, "metrics", base)
        pvalues: dict[str, float] = {}
        regressions: list[str] = []
        for name, cur_res in cur_metrics.items():
            base_res = base_metrics.get(name) if hasattr(base_metrics, "get") else None
            cur_samples = list(getattr(cur_res, "samples", []) or [])
            base_samples = list(getattr(base_res, "samples", []) or []) if base_res else []
            if not cur_samples or not base_samples:
                logger.debug("skip MW for %s (no samples)", name)
                continue
            res = mann_whitney_u(cur_samples, base_samples, alternative="two-sided")
            pvalues[name] = res.pvalue
            if res.pvalue < float(alpha):
                regressions.append(f"{name} (p={res.pvalue:.4g})")
        if regressions:
            raise MetricThresholdViolated(
                f"behavioural regression in: {', '.join(regressions)} (alpha={alpha:g})",
                metric="behavioral_report",
            )
        return pvalues

    @keyword(name="Get Session Health")
    def get_session_health(self, session: Session) -> str:
        """Return ``healthy`` / ``degraded`` / ``unknown`` from the metric pack."""
        try:
            report = self.compute_42796_metric_pack(session)
        except RuntimeError:
            return "unknown"
        # ``BehavioralReport.overall_health`` is the canonical attribute;
        # tolerate ``health`` as a back-compat alias.
        return str(getattr(report, "overall_health", None) or getattr(report, "health", "unknown"))

    # ---- internal helper (no @keyword decorator) -----------------------
    def load_behavioral_report(self, source: BehavioralReport | str | None) -> BehavioralReport | None:
        if source is None or not isinstance(source, str):
            return source
        _, _, types_mod = _import_metrics()
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
        ctor = getattr(types_mod, "BehavioralReport", None)
        if ctor is None:
            raise SessionParseFailed("metrics.types.BehavioralReport missing")
        try:
            return ctor(**payload)  # type: ignore[no-any-return]
        except TypeError:
            return payload  # type: ignore[no-any-return]  # plain dict fallback


CodingAgentLibrary = CodingAgentKeywords
