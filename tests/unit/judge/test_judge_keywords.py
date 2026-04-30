"""End-to-end JudgeKeywords tests using MockProvider for offline determinism."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from AgentGuard.judge.calibration import (
    DEFAULT_KAPPA_THRESHOLD,
    JudgeNotCalibratedError,
)
from AgentGuard.judge.library import JudgeKeywords
from AgentGuard.judge.rubric import load_rubric
from AgentGuard.judge.types import CalibrationSample
from AgentGuard.providers.base import ChatResponse
from AgentGuard.providers.mock import MockProvider

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "judge"


def _mk_response(payload: dict[str, str]) -> ChatResponse:
    return ChatResponse(
        text=f"Reasoning: looks fine.\n{json.dumps(payload)}\n",
    )


@pytest.fixture(name="rubric_path")
def _rubric_path() -> Path:
    return FIXTURE_DIR / "sample_rubric.md"


def test_load_rubric_keyword(rubric_path: Path) -> None:
    kw = JudgeKeywords()
    rubric = kw.load_rubric(rubric_path)
    assert {c.name for c in rubric.criteria} == {"correctness", "completeness"}


def test_judge_uses_mock_response_when_no_provider(rubric_path: Path) -> None:
    kw = JudgeKeywords()
    score = kw.llm_judge_should_score_at_least(
        responses="The answer is 42.",
        rubric=rubric_path,
        threshold=0.9,
        mock_response='Reasoning: ok\n{"correctness": "good", "completeness": "complete"}',
    )
    assert score == pytest.approx(1.0)


def test_judge_below_threshold_raises(rubric_path: Path) -> None:
    kw = JudgeKeywords()
    with pytest.raises(AssertionError):
        kw.llm_judge_should_score_at_least(
            responses="bad answer",
            rubric=rubric_path,
            threshold=0.9,
            mock_response='{"correctness": "bad", "completeness": "missing"}',
        )


def test_judge_uses_provider(rubric_path: Path) -> None:
    provider = MockProvider(
        responses=[
            _mk_response({"correctness": "good", "completeness": "complete"}),
            _mk_response({"correctness": "good", "completeness": "incomplete"}),
        ]
    )
    kw = JudgeKeywords(provider=provider)
    score = kw.llm_judge_should_score_at_least(
        responses=["resp1", "resp2"],
        rubric=rubric_path,
        threshold=0.5,
    )
    # mean of (1.0+1.0)/2 and (1.0+0.5)/2 = (1.0 + 0.75)/2 = 0.875
    assert score == pytest.approx(0.875)
    assert len(provider.calls) == 2


def test_pairwise_winner_extraction(rubric_path: Path) -> None:
    provider = MockProvider(responses=[ChatResponse(text='B looks better.\n{"winner": "B"}')])
    kw = JudgeKeywords(provider=provider)
    winner = kw.llm_judge_pairwise("a output", "b output", rubric_path)
    assert winner == "B"


def test_pairwise_falls_back_to_trailing_token(rubric_path: Path) -> None:
    provider = MockProvider(responses=[ChatResponse(text="A is clearly better. A")])
    kw = JudgeKeywords(provider=provider)
    assert kw.llm_judge_pairwise("a", "b", rubric_path) == "A"


def test_reference_based(rubric_path: Path) -> None:
    provider = MockProvider(
        responses=[
            _mk_response({"correctness": "good", "completeness": "complete"}),
            _mk_response({"correctness": "bad", "completeness": "missing"}),
        ]
    )
    kw = JudgeKeywords(provider=provider)
    results = kw.llm_judge_reference_based(
        responses=["yes", "no"],
        references=["yes", "yes"],
        rubric=rubric_path,
    )
    assert len(results) == 2
    assert results[0].score == pytest.approx(1.0)
    assert results[1].score == pytest.approx(0.0)


def test_calibrate_judge_passes_with_perfect_predictions(rubric_path: Path, tmp_path: Path) -> None:
    samples = [
        CalibrationSample(
            input="q1",
            response="r1",
            human_label={"correctness": "good", "completeness": "complete"},
        ),
        CalibrationSample(
            input="q2",
            response="r2",
            human_label={"correctness": "bad", "completeness": "missing"},
        ),
        CalibrationSample(
            input="q3",
            response="r3",
            human_label={"correctness": "good", "completeness": "complete"},
        ),
        CalibrationSample(
            input="q4",
            response="r4",
            human_label={"correctness": "bad", "completeness": "missing"},
        ),
    ]
    provider = MockProvider(responses=[_mk_response(s.human_label) for s in samples])
    kw = JudgeKeywords(provider=provider, cache_path=tmp_path / "judge.json")
    report = kw.calibrate_judge(
        model="mock/test",
        calibration_set=samples,
        rubric=rubric_path,
        min_kappa=DEFAULT_KAPPA_THRESHOLD,
    )
    assert report.passed
    assert report.kappa == pytest.approx(1.0)
    # Cache was written:
    assert (tmp_path / "judge.json").exists()


def test_calibrate_judge_fails_below_threshold(rubric_path: Path, tmp_path: Path) -> None:
    samples = [
        CalibrationSample(
            input="q",
            response="r",
            human_label={"correctness": "good", "completeness": "complete"},
        ),
        CalibrationSample(
            input="q",
            response="r",
            human_label={"correctness": "bad", "completeness": "missing"},
        ),
    ]
    # Predict the WRONG label every time.
    provider = MockProvider(
        responses=[
            _mk_response({"correctness": "bad", "completeness": "missing"}),
            _mk_response({"correctness": "good", "completeness": "complete"}),
        ]
    )
    kw = JudgeKeywords(provider=provider, cache_path=tmp_path / "judge.json")
    with pytest.raises(AssertionError):
        kw.calibrate_judge(
            model="mock/test",
            calibration_set=samples,
            rubric=rubric_path,
            min_kappa=0.7,
        )


def test_calibrate_judge_record_only_does_not_raise(rubric_path: Path, tmp_path: Path) -> None:
    samples = [
        CalibrationSample(
            input="q",
            response="r",
            human_label={"correctness": "good", "completeness": "complete"},
        ),
        CalibrationSample(
            input="q",
            response="r",
            human_label={"correctness": "bad", "completeness": "missing"},
        ),
    ]
    provider = MockProvider(
        responses=[
            _mk_response({"correctness": "bad", "completeness": "missing"}),
            _mk_response({"correctness": "good", "completeness": "complete"}),
        ]
    )
    kw = JudgeKeywords(provider=provider, cache_path=tmp_path / "judge.json")
    report = kw.calibrate_judge(
        model="mock/test",
        calibration_set=samples,
        rubric=rubric_path,
        min_kappa=0.95,
        record_only=True,
    )
    assert not report.passed  # κ would fail under threshold but record_only suppresses


def test_calibrate_judge_loads_jsonl_fixture(tmp_path: Path, rubric_path: Path) -> None:
    # Reuse the project's calibration fixture; predict perfectly via mock_responses.
    samples_path = FIXTURE_DIR / "calibration_set.jsonl"
    rubric = load_rubric(rubric_path)
    items = []
    for line in samples_path.read_text().splitlines():
        if not line.strip():
            continue
        items.append(json.loads(line))
    provider = MockProvider(responses=[_mk_response(item["human_label"]) for item in items])
    kw = JudgeKeywords(provider=provider, cache_path=tmp_path / "judge.json")
    report = kw.calibrate_judge(
        model="mock/jsonl",
        calibration_set=samples_path,
        rubric=rubric_path,
        min_kappa=0.95,
    )
    assert report.n_items == len(items)
    assert report.kappa >= 0.95


def test_judge_should_be_calibrated_lookup(rubric_path: Path, tmp_path: Path) -> None:
    samples = [
        CalibrationSample(
            input="q",
            response="r",
            human_label={"correctness": "good", "completeness": "complete"},
        ),
        CalibrationSample(
            input="q",
            response="r",
            human_label={"correctness": "bad", "completeness": "missing"},
        ),
    ]
    provider = MockProvider(responses=[_mk_response(s.human_label) for s in samples])
    kw = JudgeKeywords(provider=provider, cache_path=tmp_path / "judge.json")
    kw.calibrate_judge(
        model="mock/test",
        calibration_set=samples,
        rubric=rubric_path,
        min_kappa=0.9,
    )

    # Now lookup should succeed without re-running the judge.
    bare = JudgeKeywords(cache_path=tmp_path / "judge.json")
    found = bare.judge_should_be_calibrated("mock/test")
    assert found.kappa >= 0.9


def test_judge_should_be_calibrated_raises_when_missing(tmp_path: Path) -> None:
    kw = JudgeKeywords(cache_path=tmp_path / "missing.json")
    with pytest.raises(JudgeNotCalibratedError):
        kw.judge_should_be_calibrated("mock/no-such-model")


def test_tool_output_semantically_equal(rubric_path: Path) -> None:
    kw = JudgeKeywords()
    res = kw.tool_output_should_be_semantically_equal(
        actual="Paris is the capital.",
        expected="The capital of France is Paris.",
        mock_response='Looks equivalent.\n{"equivalence": "equivalent"}',
    )
    assert res.score == pytest.approx(1.0)
    with pytest.raises(AssertionError):
        kw.tool_output_should_be_semantically_equal(
            actual="Lyon",
            expected="Paris",
            mock_response='{"equivalence": "not-equivalent"}',
        )
