#!/usr/bin/env bash
# inject_context.sh — PreToolUse hook that injects an additional_context note.
# Always allows; demonstrates the "Hook Should Inject Context" assertion path.
set -euo pipefail

# Drain stdin so the parent doesn't block on a write-side EPIPE.
cat >/dev/null

printf '%s\n' '{"decision": "allow", "additional_context": "read-only system path"}'
exit 0
