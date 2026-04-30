"""Top-level type aliases re-exported by the CodingAgent library surface.

These aliases let callers (and tests) write ``from AgentGuard.coding_agent
import Session, BehavioralReport`` without having to know whether the symbol
lives in the ``session`` or ``metrics`` sub-package — and they keep the
public surface stable if those sub-packages are reorganised.

Sibling modules are imported lazily; if they are missing on disk (parallel
agent race during Phase 3), aliases fall back to ``Any`` so that
``library.py`` stays import-clean. The library's keyword bodies do their own
lazy-import-with-runtime-error so the user sees a clear failure message.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "Session",
    "DriverConfig",
    "DriverResult",
    "MetricResult",
    "BehavioralReport",
    "MetricCalculator",
]

# A metric calculator is any callable that consumes a Session and returns a
# MetricResult — defined here (not in ``metrics.types``) because the contract
# is owned by the library surface, not the calculator implementation.
MetricCalculator = Any

if TYPE_CHECKING:  # pragma: no cover — imports for type-checkers only.
    from AgentGuard.coding_agent.drivers.base import (  # noqa: F401
        DriverConfig,
        DriverResult,
    )
    from AgentGuard.coding_agent.metrics.types import (  # noqa: F401
        BehavioralReport,
        MetricResult,
    )
    from AgentGuard.coding_agent.session.types import Session  # noqa: F401
else:
    # Runtime aliases — fall back to ``Any`` if a sibling module hasn't landed.
    try:
        from AgentGuard.coding_agent.session.types import Session  # noqa: F401
    except ImportError:  # pragma: no cover — Phase 3 race
        Session = Any

    try:
        from AgentGuard.coding_agent.drivers.base import (  # noqa: F401
            DriverConfig,
            DriverResult,
        )
    except ImportError:  # pragma: no cover — Phase 3 race
        DriverConfig = Any
        DriverResult = Any

    try:
        from AgentGuard.coding_agent.metrics.types import (  # noqa: F401
            BehavioralReport,
            MetricResult,
        )
    except ImportError:  # pragma: no cover — Phase 3 race
        MetricResult = Any
        BehavioralReport = Any
