#!/usr/bin/env python3
"""echo_decision.py — Test fixture: echo back a decision sourced from envelope.

Reads the Claude Code envelope on stdin; emits ``{"decision": <value>}`` where
``value`` comes from the envelope's ``test_decision`` field (default
``"allow"``). When the decision is ``block`` we also exit 2 to mirror the
Claude Code semantics.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    raw = sys.stdin.read()
    try:
        envelope = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        envelope = {}

    decision = str(envelope.get("test_decision", "allow")).strip().lower() or "allow"
    reason = str(envelope.get("test_reason", ""))
    payload: dict[str, object] = {"decision": decision}
    if reason:
        payload["reason"] = reason

    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return 2 if decision == "block" else 0


if __name__ == "__main__":
    sys.exit(main())
