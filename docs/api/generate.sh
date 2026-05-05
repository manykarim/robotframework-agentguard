#!/usr/bin/env bash
# Regenerate Robot Framework `libdoc` HTML for every AgentGuard sub-library.
#
# Usage:
#   docs/api/generate.sh           # writes HTML next to this script
#   docs/api/generate.sh --json    # writes JSON sidecars too
#
# Phase-4-D (PROPOSAL-library-import-structure): the 11 PascalCase singular
# façade modules are documented as the canonical user-facing import path
# (`AgentGuard.MCP`, `AgentGuard.Skill`, …). Internal deep-path classes
# (`AgentGuard.mcp.library.MCPKeywords`) are also rendered for advanced
# users — same payload, different stem.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DIR="$SCRIPT_DIR"

WANT_JSON=0
if [[ "${1:-}" == "--json" ]]; then
  WANT_JSON=1
fi

cd "$REPO_ROOT"

# Top-level Library — the kitchen-sink (Library AgentGuard).
TOP=(
  "AgentGuard:src/AgentGuard/library.py"
)

# 11 PascalCase singular façades — the canonical user-facing imports.
# `AgentGuard.MCP.html`, `AgentGuard.Skill.html`, …
FACADES=(
  "AgentGuard.MCP:src/AgentGuard/MCP.py"
  "AgentGuard.Skill:src/AgentGuard/Skill.py"
  "AgentGuard.Tool:src/AgentGuard/Tool.py"
  "AgentGuard.Stats:src/AgentGuard/Stats.py"
  "AgentGuard.Judge:src/AgentGuard/Judge.py"
  "AgentGuard.Security:src/AgentGuard/Security.py"
  "AgentGuard.Hook:src/AgentGuard/Hook.py"
  "AgentGuard.SubAgent:src/AgentGuard/SubAgent.py"
  "AgentGuard.Coding:src/AgentGuard/Coding.py"
  "AgentGuard.Benchmark:src/AgentGuard/Benchmark.py"
  "AgentGuard.Scenario:src/AgentGuard/Scenario.py"
)

generated=0
for entry in "${TOP[@]}" "${FACADES[@]}"; do
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
