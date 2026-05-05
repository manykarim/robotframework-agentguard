"""Benchmarks-only pytest fixtures and helpers.

Kept separate from `tests/conftest.py` so the unit test suite does not pull in
`pytest-benchmark` when it is missing, and so benchmark-only fixtures (echo MCP
server, sample skill text, golden BFCL cases) are colocated with their callers.

All fixtures are **type-annotated** even though benchmarks/ is excluded from
`mypy --strict` (per task brief).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

# Make src/ importable for `import AgentGuard` when running benchmarks via
# `pytest benchmarks/` from the repo root without `pip install -e .`.
_SRC = Path(__file__).parent.parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


# --------------------------- pytest-benchmark tweaks ------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register the `docker` marker so `--strict-markers` accepts it."""
    config.addinivalue_line(
        "markers",
        "docker: requires a reachable Docker daemon (sandbox-docker benchmarks)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark every collected benchmark with `slow` so unit-test runs skip them."""
    for item in items:
        item.add_marker(pytest.mark.slow)


# --------------------------- shared fixtures --------------------------------


@pytest.fixture(scope="session")
def echo_fastmcp_server() -> Any:
    """Build a minimal in-memory FastMCP server (echo + add).

    Skips when fastmcp is unavailable so a partial environment does not fail.
    """
    fastmcp = pytest.importorskip("fastmcp")

    server = fastmcp.FastMCP("agentguard-bench-echo")

    @server.tool()
    def echo(text: str) -> str:
        """Echo `text` back unchanged."""
        return text

    @server.tool()
    def add(x: int, y: int) -> int:
        """Add two integers."""
        return x + y

    return server


@pytest.fixture(scope="session")
def golden_calls() -> list[dict[str, Any]]:
    """Return 100 synthetic BFCL-shaped (predicted, expected) call pairs."""
    out: list[dict[str, Any]] = []
    for i in range(100):
        out.append(
            {
                "predicted": {
                    "name": "search",
                    "arguments": {"q": f"item-{i}", "limit": 10, "page": i % 5},
                },
                "expected": {
                    "name": "search",
                    "arguments": {"q": f"item-{i}", "limit": 10, "page": i % 5},
                },
            }
        )
    return out


@pytest.fixture
def sample_skill_dir(tmp_path: Path) -> Path:
    """Write a syntactically-valid SKILL.md to `tmp_path/sample-skill/`."""
    root = tmp_path / "sample-skill"
    root.mkdir()
    (root / "SKILL.md").write_text(
        "---\n"
        "name: sample-skill\n"
        "description: Benchmark fixture skill — echoes 'OK' on every prompt.\n"
        "allowed-tools:\n"
        "  - Read\n"
        "---\n"
        "When asked, respond with 'OK'.\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def sample_skill_text() -> str:
    """Return a syntactically-valid SKILL.md as a string (no fs touch)."""
    return (
        "---\n"
        "name: bench-skill\n"
        "description: A benchmark fixture skill used by parser/grader tests.\n"
        "allowed-tools:\n"
        "  - Read\n"
        "  - Write\n"
        "---\n"
        "Respond concisely. Always include the literal token 'OK'.\n"
    )


@pytest.fixture
def mock_chat_response() -> Any:
    """Return a `ChatResponse` factory used by judge benchmarks."""
    try:
        from AgentGuard.providers.base import ChatResponse, Usage
    except ImportError:  # pragma: no cover — defensive
        pytest.skip("AgentGuard.providers not importable")

    def _make(text: str = "OK") -> Any:
        return ChatResponse(
            text=text,
            tool_calls=[],
            usage=Usage(prompt_tokens=10, completion_tokens=5, cost_usd=Decimal("0")),
        )

    return _make


@pytest.fixture
def write_jsonl_records(tmp_path: Path) -> Any:
    """Helper that writes a list of JSON-able dicts as JSONL and returns the Path."""

    def _write(records: list[dict[str, Any]], name: str = "records.jsonl") -> Path:
        out = tmp_path / name
        out.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        return out

    return _write


# --------------------------- benchmark output dir ---------------------------


@pytest.fixture(scope="session")
def benchmark_results_dir() -> Iterator[Path]:
    """Where pytest-benchmark JSON artifacts land (CI uploads this)."""
    out = Path(__file__).parent / "results"
    out.mkdir(parents=True, exist_ok=True)
    yield out
