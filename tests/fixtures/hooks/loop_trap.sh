#!/usr/bin/env bash
# loop_trap.sh — Stop hook antipattern: always blocks regardless of
# stop_hook_active. Used to exercise Detect Stop Hook Loop.
set -euo pipefail

# Drain stdin.
cat >/dev/null

printf '%s\n' '{"decision": "block", "reason": "loop trap: keep working"}'
exit 2
