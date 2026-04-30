#!/usr/bin/env bash
# security_check.sh — PreToolUse hook: blocks any `rm -rf /` command.
# Reads the Claude Code envelope on stdin; matches tool_input.command for the
# destructive pattern. Exits 2 (block) on match, 0 (allow) otherwise.
set -euo pipefail

payload="$(cat)"

# Naive grep is enough for the deterministic test fixture — we don't want a
# python dep here. The pattern is intentionally broad: any 'rm -rf /' (or
# 'rm -rf /foo') in tool_input.command counts as destructive.
if printf '%s' "$payload" | grep -Eq '"command"[[:space:]]*:[[:space:]]*"[^"]*rm[[:space:]]+-rf[[:space:]]+/'; then
    printf '%s\n' '{"decision": "block", "reason": "destructive command detected"}'
    printf '%s\n' "destructive command" >&2
    exit 2
fi

printf '%s\n' '{"decision": "allow"}'
exit 0
