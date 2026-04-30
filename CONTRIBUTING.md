# Contributing to robotframework-agentguard

Thanks for your interest. This project is built and maintained by a swarm of
specialised agents, but humans are first-class contributors — please read this
file end-to-end before your first PR.

## TL;DR

1. Fork → branch off `main` → PR back into `main`.
2. One PR == one bounded context (see DDD map).
3. `uv run pytest -q && uv run ruff check && uv run mypy src tests` must pass.
4. Never commit secrets, never edit files outside your assigned subtree.

## Branching model

- `main` is always releasable.
- Feature branches: `feat/<bounded-context>/<short-slug>`
  e.g. `feat/skills/discovery-default-deny`.
- Fix branches: `fix/<bounded-context>/<short-slug>`.
- Docs-only branches: `docs/<short-slug>`.
- Performance branches: `perf/<bounded-context>/<short-slug>`.

Long-lived branches are discouraged; prefer small PRs (<400 LOC diff).

## Commits

Conventional Commits with the bounded context as the scope:

```
feat(skills): default-deny scanner pipeline
fix(stats): cliffs_delta returns NaN on identical samples
docs(security): clarify --allow-code-execution escape hatch
perf(mcp): cache FastMCP capability snapshot per server
chore(ci): bump astral-sh/setup-uv to v4
```

A merge commit message MUST reference the ADR if the PR changes a public API
(`Refs ADR-006`, `Refs ADR-013`). Cross-cutting changes belong to the
`foundation` agent — coordinate via memory before opening the PR.

## Swarm coordination

This repo follows the agent-ownership map in
[`.swarm-coordination.md`](.swarm-coordination.md). Each implementation agent
owns a disjoint subtree under `src/AgentGuard/` and may **only** write inside
its column. Cross-cutting changes go through the `foundation` agent.

When you need a change in someone else's subtree:

1. Write a memory key under the namespace `agentguard/phase1/needs/<owner>` describing the requirement.
2. Stub the dependency in your own code (raise `NotImplementedError` if needed).
3. Open the PR with the `blocked-on:<owner>` label.

The same rules apply to human contributors — pick the bounded context whose
ownership you are inheriting and do not stretch the diff into adjacent
contexts.

## Local setup

```bash
git clone https://github.com/manykarim/robotframework-agentguard
cd robotframework-agentguard
uv sync --group dev
uv run agentguard doctor
```

Add `.env`:

```
OPENROUTER_API_KEY=sk-or-...   # only needed for `pytest -m live`
```

## Tests

| Command                                          | When                       |
|--------------------------------------------------|----------------------------|
| `uv run pytest tests/unit -q`                    | Every save                 |
| `uv run pytest tests/integration -q -m "not live"` | Before every PR          |
| `uv run robot tests/acceptance/`                 | Before every PR            |
| `uv run pytest benchmarks/ --benchmark-only`     | Performance-sensitive PRs  |
| `uv run pytest -m live`                          | Tagged change to a live keyword |

Coverage threshold: `--cov-fail-under=80` on `src/AgentGuard`. PRs that drop
coverage below 80% will fail CI.

## Style + types

- `ruff check` and `ruff format --check` — both must pass.
- `mypy src tests` (strict) — must pass. `benchmarks/` is exempt.
- Public functions get full type annotations and a NumPy-style docstring.
- File length ceiling: **250 lines** (CLAUDE.md hard rule).

## Documentation

- New keywords MUST regenerate libdoc: `./docs/api/generate.sh`.
- New examples go under `examples/` with a one-line entry in
  `examples/README.md`.
- ADR-affecting changes update the ADR's status block (`Proposed` →
  `Accepted` / `Superseded`).

## Security

- Never commit `.env`, API keys, or PII.
- Run `npx @claude-flow/cli@latest security scan` after security-related
  changes (per CLAUDE.md).
- Report vulnerabilities privately — see [SECURITY.md](SECURITY.md).

## License

By contributing you agree to license your contribution under the
[Apache 2.0 License](LICENSE).
