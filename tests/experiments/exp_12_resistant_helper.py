"""Helpers for exp_12 — synthesise the value shapes the analyst flagged as
"edge cases that resist collapse" so we can probe whether `validate` /
`evaluate` actually accept them in a Robot context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from robot.api.deco import keyword


# Mann-Whitney result — both shapes the existing AgentGuard code already returns.

@dataclass
class MWResult:
    statistic: float
    pvalue: float
    alternative: str = "greater"


@keyword(name="Synthesize MW Result")
def synthesize_mw_result(statistic: float, pvalue: float) -> tuple[float, float]:
    """Return a plain (stat, p) tuple — minimal-shape MW result."""
    return float(statistic), float(pvalue)


@keyword(name="Synthesize MW Dataclass")
def synthesize_mw_dataclass(statistic: float, pvalue: float, alternative: str = "greater") -> MWResult:
    """Return the dataclass shape (matches AgentGuard's stats.mannwhitney.MannWhitneyResult)."""
    return MWResult(statistic=float(statistic), pvalue=float(pvalue), alternative=alternative)


# Tool-call list — domain-specific predicates over a list of dicts.

@keyword(name="Synthesize Tool Calls")
def synthesize_tool_calls(*entries: str) -> list[dict[str, Any]]:
    """Each ``entries`` arg is a JSON string for one tool-call record."""
    return [json.loads(e) for e in entries]


# Skill security report — composite pipeline output.

@dataclass
class _ScanReport:
    decision: str
    critical_findings: int


@keyword(name="Synthesize Skill Report")
def synthesize_skill_report(decision: str, critical_findings: int) -> _ScanReport:
    return _ScanReport(decision=decision, critical_findings=int(critical_findings))


# Sandbox result — the existing SandboxResult dataclass shape.

@dataclass
class _SandboxResult:
    exit_code: int
    stdout: str


@keyword(name="Synthesize Sandbox Result")
def synthesize_sandbox_result(exit_code: int, stdout: str) -> _SandboxResult:
    return _SandboxResult(exit_code=int(exit_code), stdout=stdout)


# Bootstrap CI — dict shape AgentGuard's stats module returns.

@keyword(name="Synthesize CI")
def synthesize_ci(low: float, high: float) -> dict[str, float]:
    return {"low": float(low), "high": float(high)}
