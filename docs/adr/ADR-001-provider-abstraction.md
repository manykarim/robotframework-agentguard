# ADR-001: Provider Abstraction via LiteLLM

- **Status**: Proposed
- **Date**: 2026-04-29
- **Deciders**: agentguard-architecture-swarm
- **Bounded Context**: Provider

## Context

`agentguard` must talk to many LLMs to generate tool calls, drive coding-agent CLIs, and act as judge models. The research catalogues 100+ providers reachable via LiteLLM (Anthropic, OpenAI, Gemini, Mistral, Cohere, Bedrock, Azure, Vertex, Together, Fireworks, DeepSeek, xAI, Groq, OpenRouter, Ollama, vLLM, llama.cpp, LM Studio) and notes that LiteLLM normalises responses, costs and exception types onto an OpenAI-compatible surface (research §4.4, §7.1).

However, several capabilities leak through the abstraction: Anthropic extended thinking (`effort=high|max`), OpenAI Responses API / structured outputs, Gemini grounding, Bedrock prompt caching and cross-region inference. A single fat-interface adapter would couple every provider's idiosyncrasies into one class.

We need a stable `LLMProviderAdapter` Protocol with LiteLLM as the default, and thin vendor-specific subclasses that opt-in to advanced features through `Provider Supports` capability checks.

## Decision

Default to **LiteLLM** as the provider implementation; expose `LLMProviderAdapter` (Protocol) with `chat`, `stream`, `cost`, `supports`; ship thin vendor subclasses (`AnthropicAdapter`, `OpenAIAdapter`, `GeminiAdapter`, `BedrockAdapter`, `OllamaAdapter`, `VLLMAdapter`) that add provider-only kwargs gated by `supports("extended_thinking" | "structured_outputs" | "grounding" | "prompt_caching")`.

## Rationale

- One OpenAI-compatible interface across 100+ providers (research §7.1).
- LiteLLM maps provider exceptions to OpenAI types — keywords like `LLM Call Should Not Fail With Rate Limit` stay portable.
- Cost/latency tracking is uniform via LiteLLM callbacks (MLflow, Langfuse, Helicone).
- Subclassing keeps vendor-specific knobs from polluting the common surface.
- LiteLLM Gateway can also proxy coding-agent CLIs so token/cost capture stays uniform (ADR-009).

## Consequences

- **Positive**: New providers added with zero `agentguard` code changes; unified cost reporting; portable test suites.
- **Negative**: LiteLLM update cadence becomes a dependency risk; certain bleeding-edge features lag upstream LiteLLM by days/weeks.
- **Neutral**: Vendor subclasses must be kept thin (≤200 LoC) to avoid drift; capability matrix needs CI verification.

## Alternatives Considered

- **Option A — Roll our own multi-provider client**: rejected, duplicates LiteLLM's mapped-exception/cost infrastructure and adds maintenance burden.
- **Option B — Vendor-specific adapters only (no LiteLLM)**: rejected, forces N×M provider matrix in tests, breaks portability promise.
- **Option C — `aisuite` or `instructor` as the shim**: rejected, narrower provider coverage and weaker cost/exception normalization than LiteLLM at time of writing.

## Related ADRs

- ADR-003 (Library Composition — provider injected at the top-level Library)
- ADR-009 (Coding Agent Driver — uses LiteLLM Gateway proxy)
- ADR-011 (Judge model selection rides on this adapter)
- ADR-019 (3-Tier Model Routing — the provider adapter is what gets routed)
