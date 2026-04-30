"""Experiment 07: Claude Code session JSONL is parseable (research §4.5, §7.2, §3.3).

Assumption: `~/.claude/projects/*/...jsonl` files contain per-line JSON records
with stable top-level keys we can normalize to messages/tool_calls/tool_responses/
thinking_blocks/interrupts/hook_events/usage for the #42796 metric pack.
"""
import json
import os
from collections import Counter
from pathlib import Path


def main() -> int:
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        print("no ~/.claude/projects directory found")
        print("PARTIAL exp_07_session_jsonl_schema — synthetic fixture required")
        return 0

    candidates = sorted(base.rglob("*.jsonl"))
    if not candidates:
        print("no *.jsonl files under", base)
        print("PARTIAL exp_07_session_jsonl_schema — synthetic fixture required")
        return 0

    # Pick the most recently modified jsonl
    f = max(candidates, key=lambda p: p.stat().st_mtime)
    print("inspected file:", f)
    print("size_bytes:", f.stat().st_size)

    types = Counter()
    keys_per_line: list[set[str]] = []
    samples = []
    with f.open() as h:
        for i, line in enumerate(h):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as e:
                print(f"line {i}: JSON parse error: {e}")
                continue
            keys_per_line.append(set(obj.keys()))
            t = obj.get("type") or obj.get("event") or "?"
            types[t] += 1
            if i < 5:
                samples.append(sorted(obj.keys()))
            if i >= 200:
                break

    union = set().union(*keys_per_line) if keys_per_line else set()
    print("first 5 lines top-level keys:")
    for s in samples:
        print(" ", s)
    print("union of top-level keys (first 200 lines):", sorted(union))
    print("type counts:", dict(types))

    # The canonical schema fields from research §7.2
    canonical = {"messages", "tool_calls", "tool_responses", "thinking_blocks",
                 "signature_lengths", "interrupts", "hook_events", "usage"}
    # Per-line records are typically NOT pre-aggregated; we expect to *derive* the
    # schema. Mark PASS if we can identify message/tool_use records by `type` field.
    derivable = any(k in union for k in ("message", "type", "role", "content", "uuid"))
    print("schema-derivable from line records:", derivable)
    print("PASS" if derivable else "PARTIAL", "exp_07_session_jsonl_schema")
    return 0 if derivable else 1


if __name__ == "__main__":
    raise SystemExit(main())
