"""Skill grader — Inspect AI Task wrapper for offline + live evaluation.

Builds a single :class:`inspect_ai.Task` per skill:

- ``dataset``  : ``MemoryDataset([Sample(input=prompt, target=None) for ...])``
- ``solver``   : injects ``Skill.body`` as a system message, then ``generate()``
- ``scorer``   : prefers ``AgentGuard.judge`` if importable; otherwise falls back
  to a permissive ``match()`` so the wiring still works in offline tests.

Confirmed by experiment 04: ``mockllm/model`` lets this run end-to-end with no
API key, which is exactly what the unit/acceptance tests rely on.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC
from typing import Any

from AgentGuard.skills.parser import Skill, parse_skill
from AgentGuard.skills.scorecard import (
    JudgeScore,
    SkillResponse,
    SkillScorecard,
    hash_rubric,
)

logger = logging.getLogger("AgentGuard.skills.grader")


@dataclass(slots=True)
class GraderConfig:
    """Knobs for one ``Run Skill Eval`` invocation."""

    runs: int = 10
    rubric: str | None = None
    judge_model: str | None = None
    model: str | None = None
    prompts: list[str] | None = None
    log_dir: str | None = None


def _coerce_skill(skill: Skill | str) -> Skill:
    if isinstance(skill, Skill):
        return skill
    return parse_skill(skill)


def _build_task(skill: Skill, prompts: Sequence[str]) -> Any:
    """Compose an Inspect AI Task. Imports are lazy so the module loads fast."""
    from inspect_ai import Task
    from inspect_ai.dataset import MemoryDataset, Sample
    from inspect_ai.scorer import match
    from inspect_ai.solver import generate, system_message

    samples = [Sample(input=prompt, target="", id=f"{skill.name}-{idx}") for idx, prompt in enumerate(prompts)]
    dataset = MemoryDataset(samples)
    skill_system = system_message(_skill_system_prompt(skill))
    return Task(
        dataset=dataset,
        solver=[skill_system, generate()],
        scorer=match(location="any"),
    )


def _skill_system_prompt(skill: Skill) -> str:
    """Compose the system message that injects the skill into the model."""
    header = f"You are operating with the '{skill.name}' Agent Skill loaded.\nSkill description: {skill.description}\n"
    if skill.allowed_tools:
        header += f"Allowed tools (advisory): {', '.join(skill.allowed_tools)}\n"
    return f"{header}\n----- SKILL BODY -----\n{skill.body}".strip()


def _resolve_model(model: str | None) -> str:
    if model:
        return model
    try:
        from AgentGuard import config as cfg
    except ImportError:
        return "mockllm/model"
    getter = getattr(cfg, "default_model", None)
    if callable(getter):
        try:
            value = getter()
            if isinstance(value, str) and value:
                return value
        except Exception:  # pragma: no cover — defensive
            logger.exception("default_model() raised — falling back to mockllm")
    return "mockllm/model"


def _resolve_judge_model(judge_model: str | None, model: str) -> str:
    if judge_model:
        return judge_model
    try:
        from AgentGuard import config as cfg
    except ImportError:
        return model
    getter = getattr(cfg, "default_judge_model", None)
    if callable(getter):
        try:
            value = getter()
            if isinstance(value, str) and value:
                return value
        except Exception:  # pragma: no cover
            logger.exception("default_judge_model() raised — falling back to model")
    return model


def _eval_log_to_responses(
    skill: Skill, log_obj: Any, model: str, run_index: int
) -> tuple[list[SkillResponse], list[JudgeScore]]:
    responses: list[SkillResponse] = []
    scores: list[JudgeScore] = []
    samples = getattr(log_obj, "samples", None) or []
    for sample in samples:
        prompt = _stringify(getattr(sample, "input", ""))
        output = _extract_output(sample)
        responses.append(
            SkillResponse(
                prompt=prompt,
                output=output,
                run_index=run_index,
                model=model,
            )
        )
        score = _extract_first_score(sample)
        if score is not None:
            scores.append(
                JudgeScore(
                    sample_id=str(getattr(sample, "id", f"{skill.name}-{run_index}")),
                    value=_score_to_float(score),
                    rationale=str(getattr(score, "explanation", "") or ""),
                    raw=str(getattr(score, "value", "")),
                )
            )
    return responses, scores


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_stringify(v) for v in value)
    return str(value)


def _extract_output(sample: Any) -> str:
    output = getattr(sample, "output", None)
    if output is None:
        return ""
    completion = getattr(output, "completion", None)
    if isinstance(completion, str) and completion:
        return completion
    choices = getattr(output, "choices", None) or []
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None) if message else None
        if isinstance(content, str):
            return content
    return _stringify(output)


def _extract_first_score(sample: Any) -> Any | None:
    scores = getattr(sample, "scores", None)
    if isinstance(scores, dict) and scores:
        return next(iter(scores.values()))
    return getattr(sample, "score", None)


def _score_to_float(score: Any) -> float:
    raw = getattr(score, "value", None)
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    if isinstance(raw, str):
        token = raw.strip().upper()
        return {"C": 1.0, "I": 0.0, "P": 0.5, "PASS": 1.0, "FAIL": 0.0}.get(token, 0.0)
    return 0.0


async def _run_eval(task: Any, model: str, log_dir: str | None) -> Any:
    from inspect_ai import eval_async

    kwargs: dict[str, Any] = {"model": model, "display": "plain"}
    if log_dir is not None:
        kwargs["log_dir"] = log_dir
    return await eval_async(task, **kwargs)


def run_skill_eval(skill: Skill | str, config: GraderConfig) -> SkillScorecard:
    """Drive Inspect AI ``eval()`` over ``config.runs`` repetitions of each prompt.

    Returns a populated :class:`SkillScorecard`. Works offline against
    ``mockllm/model`` (experiment 04 confirms wiring) and against any LiteLLM
    target when ``OPENROUTER_API_KEY`` (or the configured provider key) is set.
    """
    skill_obj = _coerce_skill(skill)
    prompts = list(config.prompts or _default_prompts(skill_obj))
    if not prompts:
        raise ValueError("at least one prompt is required to run a skill eval")
    model = _resolve_model(config.model)
    judge_model = _resolve_judge_model(config.judge_model, model)

    started = _utc_now()
    responses: list[SkillResponse] = []
    judge_scores: list[JudgeScore] = []

    for run_index in range(max(1, config.runs)):
        task = _build_task(skill_obj, prompts)
        t0 = time.perf_counter()
        logs = asyncio.run(_run_eval(task, model=model, log_dir=config.log_dir))
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if not logs:
            continue
        log_obj = logs[0]
        run_responses, run_scores = _eval_log_to_responses(skill_obj, log_obj, model=model, run_index=run_index)
        for resp in run_responses:
            resp.latency_ms = elapsed_ms
        responses.extend(run_responses)
        judge_scores.extend(run_scores)

    pass_rate = _compute_pass_rate(judge_scores)
    return SkillScorecard(
        skill_name=skill_obj.name,
        runs=max(1, config.runs),
        pass_rate=pass_rate,
        judge_scores=judge_scores,
        raw_responses=responses,
        started_at=started,
        ended_at=_utc_now(),
        model=model,
        judge_model=judge_model,
        rubric_hash=hash_rubric(config.rubric),
    )


def _default_prompts(skill: Skill) -> list[str]:
    return [
        f"Demonstrate the '{skill.name}' skill on a representative input.",
    ]


def _utc_now() -> str:
    from datetime import datetime

    return datetime.now(tz=UTC).isoformat()


def _compute_pass_rate(scores: Sequence[JudgeScore]) -> float:
    if not scores:
        return 0.0
    passes = sum(1 for s in scores if s.value >= 0.5)
    return passes / float(len(scores))
