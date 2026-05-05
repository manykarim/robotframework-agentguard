"""Validates the Phase-3 session-parser budget — `mean ≤ 50 ms / parse`.

Source: Phase-3 brief (`docs/PLAN.md` §8 Phase 3, `.swarm-coordination.md`
budget table). The Claude Code JSONL parser is the IP of the CodingAgent
context: every #42796 metric pack starts by walking a session log, so the
parse cost amortises into every behavioural assertion downstream.

A "large" fixture for our purposes is a synthetic 200-line Claude Code
JSONL with realistic ``tool_use`` / ``toolUseResult`` pairing — this is
representative of a 10-minute Claude Code edit session per exp_07. Because
the session-parser sub-agent owns ``tests/fixtures/coding_agent/sessions/``,
we synthesise the 200-line fixture in ``tmp_path`` rather than relying on
a committed file (the committed ``claude_code_minimal.jsonl`` is only 11
lines and therefore not load-bearing here).

Skips cleanly when the parser module has not yet been wired by the
session-parser sibling agent.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

# Budget — Phase-3 session-parser ceiling.
BUDGET_MEAN_MS = 50.0


def _build_with_tools_jsonl(target: Path, *, lines: int = 200) -> Path:
    """Synthesise a Claude Code JSONL with ``lines`` non-empty records.

    The shape mirrors what ``LocalDriver`` emits and what real
    ``~/.claude/projects/`` files contain (per exp_07): ``system`` ->
    ``user`` -> ``assistant`` (with ``tool_use`` content blocks) ->
    ``user`` (carrying the ``toolUseResult``). ``parentUuid`` chains so the
    parser's tool-call pairing path is exercised end-to-end.
    """
    session_id = "bench-200-line-001"
    cwd = "/tmp/agentguard-bench"
    base_ts = "2026-04-29T10:00:00.000Z"

    records: list[dict[str, Any]] = []
    sys_uuid = "u-sys-1"
    records.append(
        {
            "type": "system",
            "uuid": sys_uuid,
            "parentUuid": "",
            "sessionId": session_id,
            "timestamp": base_ts,
            "message": {"role": "system", "content": "bench session"},
            "cwd": cwd,
            "gitBranch": "main",
            "version": "agentguard-bench-0.1",
        }
    )
    parent = sys_uuid

    # Each "turn" emits 2 records (assistant w/ tool_use + user w/ toolUseResult).
    # Plus a periodic user message to match realistic interleaving.
    turn = 0
    tool_names = ("Read", "Edit", "Bash", "Grep", "Write")
    while len(records) < lines:
        if turn % 5 == 0:
            user_uuid = f"u-user-{turn}"
            records.append(
                {
                    "type": "user",
                    "uuid": user_uuid,
                    "parentUuid": parent,
                    "sessionId": session_id,
                    "timestamp": base_ts,
                    "message": {"role": "user", "content": f"step {turn}"},
                    "cwd": cwd,
                    "gitBranch": "main",
                    "version": "agentguard-bench-0.1",
                }
            )
            parent = user_uuid
            if len(records) >= lines:
                break

        asst_uuid = f"u-asst-{turn}"
        tool_use_id = f"toolu_{uuid.uuid4().hex[:12]}"
        tool_name = tool_names[turn % len(tool_names)]
        records.append(
            {
                "type": "assistant",
                "uuid": asst_uuid,
                "parentUuid": parent,
                "sessionId": session_id,
                "timestamp": base_ts,
                "message": {
                    "id": f"msg_{uuid.uuid4().hex[:12]}",
                    "role": "assistant",
                    "model": "claude-sonnet-4-5",
                    "content": [
                        {"type": "text", "text": f"Calling {tool_name}"},
                        {
                            "type": "tool_use",
                            "id": tool_use_id,
                            "name": tool_name,
                            "input": {"path": f"/repo/file{turn}.py"},
                        },
                    ],
                    "usage": {
                        "input_tokens": 30 + turn,
                        "output_tokens": 12,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                },
                "cwd": cwd,
                "gitBranch": "main",
                "version": "agentguard-bench-0.1",
            }
        )
        parent = asst_uuid
        if len(records) >= lines:
            break

        result_uuid = f"u-tool-{turn}"
        records.append(
            {
                "type": "user",
                "uuid": result_uuid,
                "parentUuid": parent,
                "sessionId": session_id,
                "timestamp": base_ts,
                "userType": "tool-result",
                "toolUseResult": {
                    "tool_use_id": tool_use_id,
                    "name": tool_name,
                    "content": "ok",
                },
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": "ok",
                        }
                    ],
                },
                "cwd": cwd,
                "gitBranch": "main",
                "version": "agentguard-bench-0.1",
            }
        )
        parent = result_uuid
        turn += 1

    target.write_text("\n".join(json.dumps(r) for r in records[:lines]) + "\n")
    return target


@pytest.fixture(scope="module")
def with_tools_fixture(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("session-parse") / "claude_code_with_tools.jsonl"
    return _build_with_tools_jsonl(target, lines=200)


@pytest.mark.benchmark(group="coding-agent-parse")
def test_parse_session_jsonl_200_line_budget(benchmark: Any, with_tools_fixture: Path) -> None:
    """Parse a 200-line claude-code JSONL — mean ≤ 50 ms."""
    try:
        from AgentGuard.coding_agent.session import parser
    except ImportError:
        pytest.skip("AgentGuard.coding_agent.session.parser not implemented yet")

    # Sanity-check the fixture before timing — this is excluded from the
    # measured rounds so warmup-time fixture validation never inflates mean.
    assert with_tools_fixture.exists()
    line_count = sum(1 for _ in with_tools_fixture.open(encoding="utf-8") if _.strip())
    assert line_count == 200, f"expected 200 records, got {line_count}"

    def _parse_once() -> int:
        sess = parser.parse(with_tools_fixture, format="claude-code")
        return len(sess.tool_calls)

    result = benchmark.pedantic(_parse_once, rounds=20, iterations=1, warmup_rounds=2)
    assert result > 0, "fixture parse produced no tool_calls"

    mean_ms = float(benchmark.stats.stats.mean) * 1000.0
    if mean_ms > BUDGET_MEAN_MS:
        pytest.fail(
            f"session parse mean {mean_ms:.3f} ms exceeds budget {BUDGET_MEAN_MS} ms (Phase-3 session-parser budget)"
        )
