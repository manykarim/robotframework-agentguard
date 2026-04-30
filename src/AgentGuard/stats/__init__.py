"""Statistics context — non-deterministic test assertions (ADR-005).

Exposes scipy-backed primitives plus locally-implemented Cliff's delta,
Vargha-Delaney A12, TARr@N / TARa@N, and HumanEval pass@k. The
`StatsKeywords` class is the Robot Framework surface composed by
`AgentGuard.library.AgentGuard` via `DynamicCore`.

All public functions are deterministic (Tier-1) and require no API key.

Research: docs/research/research.md §2.7, §3.4. Surface confirmed by
docs/research/experiments/exp_06_scipy_stats.log against scipy 1.17.1.
"""

from AgentGuard.stats.bootstrap import bootstrap_ci
from AgentGuard.stats.cliffs_delta import cliffs_delta
from AgentGuard.stats.library import StatsKeywords
from AgentGuard.stats.mannwhitney import mann_whitney_u
from AgentGuard.stats.pass_at_k import pass_at_k
from AgentGuard.stats.tar import tar_a, tar_r
from AgentGuard.stats.vargha_delaney import vargha_delaney_a12

__all__ = [
    "StatsKeywords",
    "bootstrap_ci",
    "cliffs_delta",
    "mann_whitney_u",
    "pass_at_k",
    "tar_a",
    "tar_r",
    "vargha_delaney_a12",
]
