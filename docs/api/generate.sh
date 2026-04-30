#!/usr/bin/env bash
# Regenerate Robot Framework `libdoc` HTML for every AgentGuard sub-library.
#
# Usage:
#   docs/api/generate.sh           # writes HTML next to this script
#   docs/api/generate.sh --json    # writes JSON sidecars too
#
# Requires: `uv` and a working `uv sync`. Sub-libraries that are not yet
# implemented are silently skipped — the Phase-1 minimum is the top-level
# AgentGuard library.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DIR="$SCRIPT_DIR"

WANT_JSON=0
if [[ "${1:-}" == "--json" ]]; then
  WANT_JSON=1
fi

cd "$REPO_ROOT"

# Map of <output stem> => <source path>. Order matters: top-level first.
LIBS=(
  "AgentGuard:src/AgentGuard/library.py"
  "AgentGuard.MCP:src/AgentGuard/mcp/library.py"
  "AgentGuard.Skills:src/AgentGuard/skills/library.py"
  "AgentGuard.Stats:src/AgentGuard/stats/library.py"
  "AgentGuard.Judge:src/AgentGuard/judge/library.py"
  "AgentGuard.ToolCalls:src/AgentGuard/tool_calls/library.py"
  "AgentGuard.Security:src/AgentGuard/security/library.py"
  # Phase 2 — sub-libraries are skipped if their `library.py` is not yet
  # present (e.g. mid-Phase-2 swarm execution). See foundation-p2 in
  # `.swarm-coordination.md` for ownership.
  "AgentGuard.Hooks:src/AgentGuard/hooks/library.py"
  "AgentGuard.SubAgents:src/AgentGuard/subagents/library.py"
  # Phase 3 — CodingAgent. Skipped until library-keywords agent commits
  # `coding_agent/library.py`; see foundation-p3 in `.swarm-coordination.md`.
  "AgentGuard.CodingAgent:src/AgentGuard/coding_agent/library.py"
)

generated=0
for entry in "${LIBS[@]}"; do
  stem="${entry%%:*}"
  src="${entry##*:}"
  if [[ ! -f "$src" ]]; then
    echo "skip   $stem  ($src not present)"
    continue
  fi
  out_html="$OUT_DIR/${stem}.html"
  echo "libdoc $stem -> $out_html"
  uv run python -m robot.libdoc "$src" "$out_html"
  if [[ "$WANT_JSON" -eq 1 ]]; then
    out_json="$OUT_DIR/${stem}.json"
    uv run python -m robot.libdoc --format JSON "$src" "$out_json"
  fi
  generated=$((generated + 1))
done

echo "generated $generated libdoc artifacts in $OUT_DIR"
