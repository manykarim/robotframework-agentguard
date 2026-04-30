# ADR-012: OpenTelemetry + Robot Framework Listener

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: Telemetry

## Context

Trace-first observability is now the norm across agent eval frameworks. `mcp-eval` emits OpenTelemetry traces; LiteLLM has OTel callbacks; the Inspect AI runtime exposes structured trace events. QA teams already use Allure, ReportPortal, and Grafana (the existing `manykarim/robot-framework-reporting` stack with PostgreSQL/InfluxDB/Grafana) — `agentguard` should slot in rather than impose a new dashboard (research §4.5).

Robot Framework's listener API (`v3`) lets a library inject content into `log.html` per test. A custom listener can tail the OTel exporter and embed key metrics, tool calls, and judge rationales as HTML snippets per test, producing a per-test scorecard, per-suite metric trends, and a baseline comparison panel without forcing users out of the Robot HTML report.

JSON export ensures downstream tools (Allure, ReportPortal, Grafana) get structured data alongside the human-readable HTML.

## Decision

Emit **OpenTelemetry traces by default**, using mcp-eval-compatible span shapes. Ship `OTelListener` (Robot Framework Listener v3) that injects spans into `log.html` (per-test scorecard, per-suite trends, baseline diff panel). Always also write JSON export for Allure, ReportPortal, and Grafana integration.

## Rationale

- OTel is the cross-tool standard; mcp-eval span compatibility means existing dashboards work unchanged.
- Robot listener integration is the lowest-friction path for QA teams already using `log.html`.
- JSON export keeps integration with the documented Grafana stack and other CI dashboards open.
- Default-on telemetry surfaces statistical caveats (ADR-005's variance header) where users actually look.

## Consequences

- **Positive**: Zero-config observability; existing dashboards work; trace-first culture from day one.
- **Negative**: OTel SDK is a non-trivial dependency for users running `agentguard` in minimal CI containers — must be optional via `agentguard[telemetry]` extra.
- **Neutral**: Listener must be order-stable across Robot 7.x/8.x — pin via ADR-014.

## Alternatives Considered

- **Option A — No telemetry; only Robot HTML reports**: rejected, blocks Grafana/Allure/ReportPortal integration that existing teams already use.
- **Option B — Custom JSON only, no OTel**: rejected, breaks compatibility with mcp-eval span format and the broader OTel ecosystem.
- **Option C — Vendor-specific tracing (e.g., LangSmith only)**: rejected, contradicts the provider-agnostic principle in ADR-001.

## Related ADRs

- ADR-001 (Provider adapter emits OTel via LiteLLM callbacks)
- ADR-010 (`Session` schema is converted into spans by listener)
- ADR-014 (Robot Framework version pinned; listener API stability)
