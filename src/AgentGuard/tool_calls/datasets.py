"""BFCL dataset loader behind a thin :class:`BFCLAdapter` (ADR-004).

We deliberately *insulate* AgentGuard from upstream churn:

* Try the live ``inspect_evals.bfcl`` import first (confirmed available by
  experiment 09 — see ``docs/research/experiments/REPORT.md``). When that
  works, use its :func:`load_records_by_category` against a sparse-checkout
  of the official Gorilla dataset.
* If the import fails OR the cache is empty AND the network is unreachable,
  fall back to the bundled JSON fixtures under
  ``tests/fixtures/tool_calls/golden_calls.json``.

Either way, the caller sees a uniform ``list[BFCLCase]``. The fallback emits
a single ``warnings.warn`` (one per process) so CI logs make the source
obvious.
"""

from __future__ import annotations

import json
import logging
import os
import warnings
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from AgentGuard.tool_calls.types import (
    JSON,
    BFCLCase,
    ExpectedCall,
    ToolDefinition,
)

logger = logging.getLogger("AgentGuard.tool_calls.datasets")


# Live import path (per experiment 09):
#   inspect_evals.bfcl              -> top-level shim re-exporting `bfcl`
#   inspect_evals.bfcl.bfcl         -> Inspect AI Task factory
#   inspect_evals.bfcl.data         -> dataset loaders
#   inspect_evals.bfcl.utils.task_categories -> CATEGORIES registry
LIVE_IMPORT_PATH = "inspect_evals.bfcl"

DEFAULT_CACHE_DIR = Path(
    os.environ.get(
        "AGENTGUARD_BFCL_CACHE",
        Path.home() / ".cache" / "agentguard" / "bfcl",
    )
)

_BUNDLED_FALLBACK = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "tool_calls"
    / "golden_calls.json"
)

# Mapping of Phase-1 short names → BFCL category names. Keeps Robot tests
# pleasant ("simple", "parallel") instead of ("simple_python", ...).
_CATEGORY_ALIASES: dict[str, str] = {
    "simple": "simple_python",
    "parallel": "parallel",
    "multiple": "multiple",
    "irrelevance": "irrelevance",
    "live_simple": "live_simple",
}


_FALLBACK_WARNED = False


class BFCLAdapter:
    """Stable façade over ``inspect_evals.bfcl``.

    All downstream code talks to *this* class, never to ``inspect_evals``
    directly. When upstream breaks an import, only this file changes.
    """

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._live_module = self._try_import_live()

    @property
    def is_live(self) -> bool:
        """``True`` when ``inspect_evals.bfcl`` is importable."""
        return self._live_module is not None

    @staticmethod
    def _try_import_live() -> Any | None:
        try:
            import importlib

            return importlib.import_module(LIVE_IMPORT_PATH)
        except Exception as exc:  # noqa: BLE001 — any failure means "fall back"
            logger.debug("live BFCL import failed (%s); will use fallback fixtures", exc)
            return None

    # ----- public API ----------------------------------------------------

    def load(self, category: str = "simple", limit: int | None = None) -> list[BFCLCase]:
        """Return up to ``limit`` :class:`BFCLCase`\\ s for ``category``.

        Tries the live ``inspect_evals.bfcl`` loader first. Any failure
        (no cache, network error, schema drift) downgrades to the bundled
        fallback fixtures and warns once.
        """
        bfcl_category = _CATEGORY_ALIASES.get(category, category)

        if self._live_module is not None:
            try:
                cases = list(self._load_live(bfcl_category, limit))
                if cases:
                    return cases
            except Exception as exc:  # noqa: BLE001 — drop to fallback below
                logger.warning(
                    "live BFCL load for %r failed (%s); falling back to fixtures",
                    bfcl_category,
                    exc,
                )

        return self._load_fallback(category, limit)

    # ----- live loader ---------------------------------------------------

    def _load_live(self, category: str, limit: int | None) -> Iterable[BFCLCase]:
        from inspect_evals.bfcl.data import load_records_by_category
        from inspect_evals.bfcl.utils.task_categories import CATEGORIES

        if category not in CATEGORIES:
            raise KeyError(f"unknown BFCL category: {category!r}")

        records = load_records_by_category(category, cache_dir=self.cache_dir)
        out: list[BFCLCase] = []
        for record_id, record in records.items():
            if limit is not None and len(out) >= limit:
                break
            out.append(_record_to_case(record_id, record, category))
        return out

    # ----- fallback loader ----------------------------------------------

    @staticmethod
    def _load_fallback(category: str, limit: int | None) -> list[BFCLCase]:
        global _FALLBACK_WARNED
        if not _FALLBACK_WARNED:
            warnings.warn(
                "BFCL dataset unavailable (no cache or import failure) — "
                f"falling back to bundled fixtures at {_BUNDLED_FALLBACK}",
                stacklevel=2,
            )
            _FALLBACK_WARNED = True

        if not _BUNDLED_FALLBACK.exists():
            raise FileNotFoundError(
                f"BFCL fallback fixtures missing: {_BUNDLED_FALLBACK}"
            )
        with _BUNDLED_FALLBACK.open(encoding="utf-8") as fh:
            raw = json.load(fh)

        cases: list[BFCLCase] = []
        for entry in raw:
            if entry.get("category", "").startswith(category) or category == "all":
                cases.append(_fixture_to_case(entry))
                if limit is not None and len(cases) >= limit:
                    break
        if not cases and category != "all":
            # Caller asked for an empty category — surface it explicitly.
            return []
        return cases


# ---------------------------------------------------------------------------
# Module-level convenience for the keyword surface
# ---------------------------------------------------------------------------


_default_adapter: BFCLAdapter | None = None


def _adapter() -> BFCLAdapter:
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = BFCLAdapter()
    return _default_adapter


def load_bfcl(category: str = "simple", limit: int | None = None) -> list[BFCLCase]:
    """Module-level shortcut around the lazy :class:`BFCLAdapter` singleton."""
    return _adapter().load(category=category, limit=limit)


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _record_to_case(record_id: str, record: Any, category: str) -> BFCLCase:
    """Convert an ``inspect_evals.bfcl`` ``BFCLRecord`` into a :class:`BFCLCase`.

    Single-turn only for Phase 1 — multi-turn lives in ``trajectory.py`` once
    the multi-turn solver lands behind a feature flag.
    """
    question = record.question or [[]]
    first_turn = question[0] if question else []
    prompt = _join_user_text(first_turn)

    tools = tuple(_func_doc_to_tool(fd) for fd in (record.function or []))
    expected = tuple(_ground_truth_to_expected(record.ground_truth or []))

    return BFCLCase(
        prompt=prompt,
        tools=tools,
        expected=expected,
        category=category,
        case_id=record_id,
    )


def _fixture_to_case(entry: dict[str, Any]) -> BFCLCase:
    tools = tuple(_func_doc_to_tool(fd) for fd in entry.get("tools", []))
    expected = tuple(
        ExpectedCall(name=ec["name"], arguments=ec.get("arguments", {}))
        for ec in entry.get("expected_calls", [])
    )
    return BFCLCase(
        prompt=entry["prompt"],
        tools=tools,
        expected=expected,
        category=entry.get("category", "simple"),
        case_id=entry.get("id", ""),
    )


def _func_doc_to_tool(func_doc: dict[str, Any]) -> ToolDefinition:
    return ToolDefinition(
        name=func_doc.get("name", ""),
        description=func_doc.get("description", ""),
        parameters=func_doc.get("parameters", {}),
    )


def _ground_truth_to_expected(
    ground_truth: list[Any],
) -> Iterable[ExpectedCall]:
    for entry in ground_truth:
        if isinstance(entry, dict):
            for name, params in entry.items():
                yield ExpectedCall(
                    name=name,
                    arguments=_collapse_possible_answers(params),
                )
        # Exec-style strings ("func(arg=value)") are skipped here — Phase-1
        # AST matcher does not parse them. The exec path is left for Phase-3
        # tool-execution metrics.


def _collapse_possible_answers(params: Any) -> dict[str, JSON]:
    """Collapse BFCL ``{param: [v1, v2]}`` to ``{param: v1}`` for keyword use.

    The full possible-answers list is preserved internally by the matcher when
    invoked via the live scorer, but the keyword API surfaces a single value
    so users can write ``${case.expected.arguments[x]}`` ergonomically.
    """
    if not isinstance(params, dict):
        return {}
    out: dict[str, JSON] = {}
    for k, v in params.items():
        if isinstance(v, list) and v:
            out[k] = v[0]
        else:
            out[k] = v
    return out


def _join_user_text(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                parts.append(content)
    return "\n".join(parts)


__all__ = [
    "BFCLAdapter",
    "DEFAULT_CACHE_DIR",
    "LIVE_IMPORT_PATH",
    "load_bfcl",
]
