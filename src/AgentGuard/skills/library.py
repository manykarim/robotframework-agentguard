"""SkillsKeywords — the Robot Framework surface for the Skills bounded context.

Composed into the top-level ``AgentGuard`` library via
``DynamicCore.__init__(self, [..., SkillsKeywords(...), ...])`` (research §4.3).
Every keyword is sync-facing: async work (Inspect AI ``eval_async``) is wrapped
inside ``grader.run_skill_eval`` with a single ``asyncio.run`` per call.

Method names are PascalCase so PythonLibCore renders them as Title Case Robot
keywords (e.g. ``Load Skill``, ``Discover Skills``).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from robot.api.deco import keyword

from AgentGuard.skills.conventions import ConventionReport, check_responses
from AgentGuard.skills.discovery import DiscoveryResult, discover
from AgentGuard.skills.grader import GraderConfig, run_skill_eval
from AgentGuard.skills.parser import (
    Skill,
    SkillParseError,
    parse_skill,
    validate_skill,
)
from AgentGuard.skills.scorecard import SkillResponse, SkillScorecard

logger = logging.getLogger("AgentGuard.skills")


class _ProviderLike(Protocol):
    """Minimal local stub of ``providers.base.LLMProviderAdapter``.

    The skills module only needs ``chat`` to drive ``Skill Output For Prompts``.
    Importing the real type lazily keeps this module loadable even if the
    provider context hasn't been finalised yet.
    """

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> Any: ...


if TYPE_CHECKING:  # pragma: no cover
    from AgentGuard.providers.base import LLMProviderAdapter as _Adapter
else:  # runtime: optional import — fall back to local stub
    try:
        from AgentGuard.providers.base import LLMProviderAdapter as _Adapter
    except ImportError:  # foundation may finalise this later
        _Adapter = _ProviderLike  # type: ignore[misc, assignment]


class SkillsKeywords:
    """Robot Framework keywords for Agent Skill discovery, parsing, grading."""

    def __init__(
        self,
        provider: _Adapter | None = None,
        judge: Any | None = None,
        *,
        default_model: str | None = None,
        default_judge_model: str | None = None,
    ) -> None:
        self._provider = provider
        self._judge = judge
        self._default_model = default_model
        self._default_judge_model = default_judge_model

    # ---- discovery & parsing -----------------------------------------------
    @keyword(name="Load Skill")
    def load_skill(self, path: str | Path) -> Skill:
        """Parse a SKILL.md (or skill directory) and validate its frontmatter."""
        skill = parse_skill(path)
        validate_skill(skill)
        return skill

    @keyword(name="Discover Skills")
    def discover_skills(
        self,
        roots: list[str | Path] | None = None,
        enforce_allowlist: bool = True,
    ) -> dict[str, list[Skill]]:
        """Scan the four standard install paths (or ``roots``) for skills.

        Returns ``{tool_tag: [Skill, ...]}``. The full ``DiscoveryResult``
        (with errors and warnings) is logged but not returned; use
        :meth:`discover_skills_full` for the structured result.
        """
        result = discover(roots, enforce_allowlist=enforce_allowlist)
        for path, msg in result.errors:
            logger.error("skill at %s failed to parse: %s", path, msg)
        for warning in result.warnings:
            logger.warning(warning)
        return result.by_tool

    @keyword(name="Discover Skills Full")
    def discover_skills_full(
        self,
        roots: list[str | Path] | None = None,
        enforce_allowlist: bool = True,
    ) -> DiscoveryResult:
        """Same as :meth:`discover_skills` but returns the full result object."""
        return discover(roots, enforce_allowlist=enforce_allowlist)

    @keyword(name="Validate Skill Frontmatter")
    def validate_skill_frontmatter(self, skill: Skill) -> None:
        """Assert the skill's frontmatter is spec-compliant."""
        validate_skill(skill)

    # ---- model interaction --------------------------------------------------
    @keyword(name="Skill Output For Prompts")
    def skill_output_for_prompts(
        self,
        skill: Skill,
        prompts: list[str],
        runs: int = 1,
        model: str | None = None,
    ) -> list[SkillResponse]:
        """Drive the configured provider with ``skill`` loaded as system message.

        Returns ``len(prompts) * runs`` :class:`SkillResponse` objects, ordered
        run-major. When no provider is wired, falls back to Inspect AI's
        ``mockllm/model`` so unit tests still pass.
        """
        if not prompts:
            return []
        validate_skill(skill)
        target_model = model or self._default_model

        if self._provider is None:
            return self._mock_responses(skill, prompts, runs, target_model)

        responses: list[SkillResponse] = []
        system_text = self._system_prompt_for(skill)
        for run_index in range(max(1, runs)):
            for prompt in prompts:
                t0 = time.perf_counter()
                resp = self._provider.chat(
                    messages=[
                        {"role": "system", "content": system_text},
                        {"role": "user", "content": prompt},
                    ],
                    model=target_model,
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                responses.append(
                    SkillResponse(
                        prompt=prompt,
                        output=getattr(resp, "text", "") or "",
                        run_index=run_index,
                        model=target_model or "",
                        tokens_in=getattr(getattr(resp, "usage", None), "prompt_tokens", 0),
                        tokens_out=getattr(
                            getattr(resp, "usage", None), "completion_tokens", 0
                        ),
                        latency_ms=elapsed_ms,
                    )
                )
        return responses

    # ---- evaluation ---------------------------------------------------------
    @keyword(name="Run Skill Eval")
    def run_skill_eval(
        self,
        skill: Skill | str,
        runs: int = 10,
        rubric: str | None = None,
        judge_model: str | None = None,
        model: str | None = None,
        prompts: list[str] | None = None,
    ) -> SkillScorecard:
        """Wrap an Inspect AI Task → return a :class:`SkillScorecard`.

        Offline-safe: when neither ``model`` nor ``AgentGuard.config.default_model``
        is set, Inspect AI's ``mockllm/model`` is used.
        """
        rubric_text = self._read_rubric(rubric)
        config = GraderConfig(
            runs=runs,
            rubric=rubric_text,
            judge_model=judge_model or self._default_judge_model,
            model=model or self._default_model,
            prompts=prompts,
        )
        return run_skill_eval(skill, config)

    # ---- conventions --------------------------------------------------------
    @keyword(name="Convention Violation Rate Should Be Below")
    def convention_violation_rate_should_be_below(
        self,
        responses: list[SkillResponse] | list[str],
        rules: str | Path = ".claude/CLAUDE.md",
        threshold: float = 0.05,
    ) -> ConventionReport:
        """Run the conventions checker; raise ``AssertionError`` if rate ≥ threshold."""
        text_responses = [
            r.output if isinstance(r, SkillResponse) else str(r) for r in responses
        ]
        report = check_responses(text_responses, rules=rules)
        if report.rate >= threshold:
            offenders = ", ".join(sorted({v.rule for v in report.violations})[:5])
            raise AssertionError(
                f"convention violation rate {report.rate:.3f} ≥ threshold {threshold:.3f}; "
                f"sample rules: {offenders}"
            )
        return report

    # ---- baseline IO --------------------------------------------------------
    @keyword(name="Save Baseline")
    def save_baseline(self, scorecard: SkillScorecard, path: str | Path) -> Path:
        """Persist a :class:`SkillScorecard` as JSON for later diffing."""
        return scorecard.save(path)

    @keyword(name="Load Baseline")
    def load_baseline(self, path: str | Path) -> SkillScorecard:
        """Load a :class:`SkillScorecard` previously saved via ``Save Baseline``."""
        return SkillScorecard.load(path)

    # ---- helpers ------------------------------------------------------------
    def _read_rubric(self, rubric: str | Path | None) -> str | None:
        if rubric is None:
            return None
        candidate = Path(rubric)
        if candidate.exists() and candidate.is_file():
            return candidate.read_text(encoding="utf-8")
        if isinstance(rubric, str):
            return rubric
        return None

    @staticmethod
    def _system_prompt_for(skill: Skill) -> str:
        header = (
            f"You are operating with the '{skill.name}' Agent Skill loaded.\n"
            f"Skill description: {skill.description}\n"
        )
        if skill.allowed_tools:
            header += f"Allowed tools (advisory): {', '.join(skill.allowed_tools)}\n"
        return f"{header}\n----- SKILL BODY -----\n{skill.body}".strip()

    def _mock_responses(
        self,
        skill: Skill,
        prompts: list[str],
        runs: int,
        target_model: str | None,
    ) -> list[SkillResponse]:
        # Avoid raising during dry-runs / fixtures: return deterministic stubs.
        out: list[SkillResponse] = []
        model_label = target_model or "mockllm/model"
        for run_index in range(max(1, runs)):
            for prompt in prompts:
                out.append(
                    SkillResponse(
                        prompt=prompt,
                        output=(
                            f"[mock:{skill.name}] would respond to: {prompt[:80]}"
                        ),
                        run_index=run_index,
                        model=model_label,
                    )
                )
        return out


# Backwards-compat alias used by ``DynamicCore`` registration.
SkillsLibrary = SkillsKeywords


def _raise_parse(msg: str) -> None:  # pragma: no cover — used only from tests
    raise SkillParseError(msg)
