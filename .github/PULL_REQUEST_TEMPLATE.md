<!--
Thanks for contributing to robotframework-agentguard!
Please read CONTRIBUTING.md and .swarm-coordination.md before opening a PR.
-->

## Summary

<!-- 1-3 sentences. Reference the ADR / DDD context this PR touches. -->

## Bounded context

Which DDD context does this PR change? (only one — cross-cutting changes go through `foundation`)

- [ ] Provider
- [ ] MCP
- [ ] Skills
- [ ] Hooks
- [ ] SubAgents
- [ ] CodingAgent
- [ ] Statistics
- [ ] Judge
- [ ] Security
- [ ] Telemetry
- [ ] BehavioralMetrics
- [ ] ToolCallCorrectness
- [ ] cross-cutting (foundation)

## Checklist

- [ ] Tests added (`tests/unit/...` or `tests/integration/...` or `tests/acceptance/...`)
- [ ] `uv run ruff check` passes
- [ ] `uv run mypy src tests` passes
- [ ] `uv run pytest -q` passes locally
- [ ] No file >250 lines (CLAUDE.md hard rule)
- [ ] No new file at repo root (CLAUDE.md hard rule)
- [ ] No secrets, `.env`, or credentials committed
- [ ] Public API change → `docs/adr/` updated and ADR moved to `Accepted`
- [ ] Public API change → `docs/api/` regenerated (`docs/api/generate.sh`)
- [ ] Performance-sensitive change → benchmark added in `benchmarks/`
- [ ] Live test added → marked `@pytest.mark.live` and gated by `OPENROUTER_API_KEY`

## Related

<!-- Closes #..., refs ADR-..., refs docs/research/research.md §... -->
