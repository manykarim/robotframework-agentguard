#!/usr/bin/env bash
# require_tests.sh — Stop hook that always blocks with "Test suite must pass".
# Honours stop_hook_active to avoid the canonical infinite-loop antipattern:
# when the flag is true we allow (Claude Code is already mid-block), otherwise
# we block.
set -euo pipefail

payload="$(cat)"

if printf '%s' "$payload" | grep -Eq '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
    printf '%s\n' '{"decision": "allow", "reason": "stop_hook_active honoured"}'
    exit 0
fi

printf '%s\n' '{"decision": "block", "reason": "Test suite must pass"}'
exit 2
