# API Reference (libdoc)

Auto-generated Robot Framework keyword documentation for every AgentGuard
sub-library. The HTML files in this directory are produced by
[`generate.sh`](generate.sh) — do **not** edit them by hand.

## Regenerate

```bash
./docs/api/generate.sh
```

This produces:

| File                       | Source                                  |
|----------------------------|-----------------------------------------|
| `AgentGuard.html`          | `src/AgentGuard/library.py` (top-level) |
| `AgentGuard.MCP.html`      | `src/AgentGuard/mcp/library.py`         |
| `AgentGuard.Skills.html`   | `src/AgentGuard/skills/library.py`      |
| `AgentGuard.Stats.html`    | `src/AgentGuard/stats/library.py`       |
| `AgentGuard.Judge.html`    | `src/AgentGuard/judge/library.py`       |
| `AgentGuard.ToolCalls.html`| `src/AgentGuard/tool_calls/library.py`  |
| `AgentGuard.Security.html` | `src/AgentGuard/security/library.py`    |

Sub-library files are skipped silently when the corresponding module is not yet
present in `src/`. The Phase-1 minimum is `AgentGuard.html`.

## Browse without rendering

`libdoc` also accepts `--format JSON` for tooling:

```bash
uv run libdoc src/AgentGuard/library.py docs/api/AgentGuard.json
```

## Versioning

Each generated file embeds the AgentGuard version in its `<title>`. CI may diff
the rendered output to flag unintentional keyword renames or signature drift —
see ADR-014 (Spec Version Pinning).
