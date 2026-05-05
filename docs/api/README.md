# API Reference (libdoc)

Auto-generated Robot Framework keyword documentation for every AgentGuard
sub-library. The HTML files in this directory are produced by
[`generate.sh`](generate.sh) — do **not** edit them by hand.

The rendered site is served via GitHub Pages from this folder:
**<https://manykarim.github.io/robotframework-agentguard/api/>** (entry
point: [`index.html`](index.html)).

## Regenerate

```bash
./docs/api/generate.sh
```

This produces 12 HTML files — 1 top-level + 11 PascalCase singular façades:

| File                          | Source                                     |
|-------------------------------|--------------------------------------------|
| `AgentGuard.html`             | `src/AgentGuard/library.py` (kitchen-sink) |
| `AgentGuard.MCP.html`         | `src/AgentGuard/MCP.py`                    |
| `AgentGuard.Skill.html`       | `src/AgentGuard/Skill.py`                  |
| `AgentGuard.Tool.html`        | `src/AgentGuard/Tool.py`                   |
| `AgentGuard.Stats.html`       | `src/AgentGuard/Stats.py`                  |
| `AgentGuard.Judge.html`       | `src/AgentGuard/Judge.py`                  |
| `AgentGuard.Security.html`    | `src/AgentGuard/Security.py`               |
| `AgentGuard.Hook.html`        | `src/AgentGuard/Hook.py`                   |
| `AgentGuard.SubAgent.html`    | `src/AgentGuard/SubAgent.py`               |
| `AgentGuard.Coding.html`      | `src/AgentGuard/Coding.py`                 |
| `AgentGuard.Benchmark.html`   | `src/AgentGuard/Benchmark.py`              |
| `AgentGuard.Scenario.html`    | `src/AgentGuard/Scenario.py`               |

## Browse without rendering

`libdoc` also accepts `--format JSON` for tooling:

```bash
uv run libdoc src/AgentGuard/library.py docs/api/AgentGuard.json
```

## Versioning

Each generated file embeds the AgentGuard version in its `<title>`. CI may diff
the rendered output to flag unintentional keyword renames or signature drift —
see ADR-014 (Spec Version Pinning).
