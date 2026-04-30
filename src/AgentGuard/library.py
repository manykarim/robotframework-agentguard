"""Top-level Robot Framework Library — composes sub-libraries via DynamicCore.

ADR-003 — `AgentGuard` is the easy on-ramp; advanced users can `Library
AgentGuard.Skills` etc. Sub-libraries are imported lazily so a missing module
(e.g. `AgentGuard.skills` not yet shipped) doesn't crash `agentguard doctor`
or `from AgentGuard import AgentGuard` for downstream tooling.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from robot.api.deco import keyword, library
from robotlibcore import DynamicCore

from AgentGuard import config
from AgentGuard._version import __version__
from AgentGuard.providers import LLMProviderAdapter, build_provider

logger = logging.getLogger("AgentGuard.library")

_SUB_LIBRARIES: tuple[tuple[str, str], ...] = (
    ("AgentGuard.mcp.library", "MCPKeywords"),
    ("AgentGuard.skills.library", "SkillsKeywords"),
    ("AgentGuard.tool_calls.library", "ToolCallKeywords"),
    ("AgentGuard.stats.library", "StatsKeywords"),
    ("AgentGuard.judge.library", "JudgeKeywords"),
    ("AgentGuard.security.library", "SecurityKeywords"),
    # Phase 2 — lazy imports; missing modules during agent races are skipped
    # silently (see _build_components ImportError/AttributeError handler).
    ("AgentGuard.hooks.library", "HooksKeywords"),
    ("AgentGuard.subagents.library", "SubAgentsKeywords"),
    # Phase 3 — CodingAgent: same lazy-import contract. Until the
    # library-keywords agent commits `coding_agent/library.py`, this entry is
    # silently skipped so the top-level `AgentGuard` import remains green.
    ("AgentGuard.coding_agent.library", "CodingAgentKeywords"),
    ("AgentGuard.coding_agent.benchmarks.library", "CodingBenchmarkKeywords"),
)


@library(scope="SUITE", version=__version__, auto_keywords=False)
class AgentGuard(DynamicCore):
    """`Library AgentGuard provider=litellm model=openrouter/...` — see README."""

    def __init__(
        self,
        provider: str = "litellm",
        model: str | None = None,
        judge_model: str | None = None,
        transport: str = "auto",
        telemetry: bool = True,
        baseline_path: str | None = None,
        env_file: str | None = ".env",
    ) -> None:
        config.load_env(env_file)

        resolved_model = model or config.default_model()
        resolved_judge = judge_model or config.default_judge_model()

        self._provider_name = provider
        self._model = resolved_model
        self._judge_model = resolved_judge
        self._transport = transport
        self._telemetry_enabled = telemetry
        self._baseline_path = baseline_path
        self._provider: LLMProviderAdapter = build_provider(provider, resolved_model)

        components = self._build_components()
        self._loaded_components: list[str] = [c.__class__.__name__ for c in components]

        DynamicCore.__init__(self, components)

    def _build_components(self) -> list[Any]:
        components: list[Any] = []
        for mod_name, cls_name in _SUB_LIBRARIES:
            try:
                mod = importlib.import_module(mod_name)
                cls = getattr(mod, cls_name)
                components.append(cls(provider=self._provider))
            except (ImportError, AttributeError) as exc:
                logger.debug(
                    "AgentGuard: sub-library %s.%s not loaded (%s)",
                    mod_name,
                    cls_name,
                    exc,
                )
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "AgentGuard: sub-library %s.%s raised on init: %s",
                    mod_name,
                    cls_name,
                    exc,
                )
                continue
        return components

    @keyword(name="Get AgentGuard Info")
    def get_agentguard_info(self) -> dict[str, Any]:
        """Return version + provider + components info (no secrets)."""
        return {
            "version": __version__,
            "provider": self._provider_name,
            "model": self._model,
            "judge_model": self._judge_model,
            "transport": self._transport,
            "telemetry": self._telemetry_enabled,
            "baseline_path": self._baseline_path,
            "components": list(self._loaded_components),
        }
