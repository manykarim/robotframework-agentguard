"""Name-keyed registry of every #42796 metric calculator.

Every entry is a thin descriptor: the calculator function, its default
threshold, and its direction. The keyword layer iterates this when wiring
``Get`` / ``Should`` Robot keyword pairs;
:func:`AgentGuard.coding_agent.metrics.pack.compute_42796_pack` walks it to
produce the one-shot :class:`BehavioralReport`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from . import (
    convention,
    edits_without_read,
    first_run_test,
    interrupts,
    read_edit,
    reasoning_loops,
    repeated_edits,
    self_admitted,
    simplest_word,
    stop_hook,
    token_efficiency,
    write_ratio,
)
from ._session_proto import SessionLike
from .types import Direction, MetricResult

__all__ = ["MetricSpec", "METRICS", "get_metric", "compute_metric", "metric_names"]


@dataclass(frozen=True)
class MetricSpec:
    """One catalog entry — calculator + defaults."""

    name: str
    compute: Callable[..., MetricResult]
    default_threshold: float | None
    direction: Direction


_MODULES = (
    read_edit, edits_without_read, reasoning_loops, interrupts, stop_hook,
    first_run_test, token_efficiency, self_admitted, write_ratio,
    repeated_edits, simplest_word, convention,
)

#: Catalog order matches research §2.6 Table 2.
METRICS: Final[dict[str, MetricSpec]] = {
    m.NAME: MetricSpec(
        name=m.NAME, compute=m.compute,
        default_threshold=m.DEFAULT_THRESHOLD, direction=m.DIRECTION,
    )
    for m in _MODULES
}


def metric_names() -> list[str]:
    return list(METRICS.keys())


def get_metric(name: str) -> MetricSpec:
    try:
        return METRICS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown #42796 metric: {name!r}") from exc


def compute_metric(
    name: str,
    session: SessionLike,
    *,
    threshold: float | None | object = ...,
) -> MetricResult:
    """Run a single calculator. Pass ``threshold=None`` to disable assertion;
    omit it to use the catalog default."""
    spec = get_metric(name)
    if threshold is ...:
        return spec.compute(session, threshold=spec.default_threshold)
    return spec.compute(session, threshold=threshold)
