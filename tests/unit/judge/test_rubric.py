"""Rubric loader + prompt formatter tests (ADR-011, research §3.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentGuard.judge.rubric import (
    Criterion,
    Label,
    Rubric,
    format_judge_prompt,
    load_rubric,
    parse_judge_response,
)

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "judge"


def test_load_rubric_from_markdown_fixture() -> None:
    rubric = load_rubric(FIXTURE_DIR / "sample_rubric.md")
    assert rubric.name.startswith("Tool output")
    names = {c.name for c in rubric.criteria}
    assert names == {"correctness", "completeness"}
    correctness = next(c for c in rubric.criteria if c.name == "correctness")
    assert {lbl.value for lbl in correctness.labels} == {"good", "partial", "bad"}
    assert correctness.label_for("good").score == pytest.approx(1.0)


def test_load_rubric_from_dict() -> None:
    rubric = load_rubric(
        {
            "name": "Test",
            "criteria": [
                {
                    "name": "x",
                    "description": "matters",
                    "labels": [
                        {"value": "yes", "score": 1.0, "description": "ok"},
                        {"value": "no", "score": 0.0, "description": "nope"},
                    ],
                }
            ],
        }
    )
    assert rubric.name == "Test"
    assert rubric.criteria[0].name == "x"
    assert rubric.criteria[0].labels[0].value == "yes"


def test_rubric_fingerprint_stable_across_loads() -> None:
    a = load_rubric(FIXTURE_DIR / "sample_rubric.md")
    b = load_rubric(FIXTURE_DIR / "sample_rubric.md")
    assert a.fingerprint() == b.fingerprint()


def test_rubric_fingerprint_changes_with_content() -> None:
    a = load_rubric({"name": "x", "criteria": [{"name": "c", "labels": []}]})
    b = load_rubric({"name": "x", "criteria": [{"name": "d", "labels": []}]})
    assert a.fingerprint() != b.fingerprint()


def test_format_prompt_includes_labels_and_schema() -> None:
    rubric = load_rubric(FIXTURE_DIR / "sample_rubric.md")
    prompt = format_judge_prompt("hello", rubric, reference="hi")
    assert "correctness" in prompt
    assert "completeness" in prompt
    assert '"good"' in prompt
    assert "Reference (ground-truth)" in prompt
    assert "hello" in prompt
    assert "hi" in prompt


def test_format_prompt_rejects_empty_rubric() -> None:
    with pytest.raises(ValueError):
        format_judge_prompt("hi", Rubric(name="x", criteria=()))


def test_parse_judge_response_extracts_trailing_json() -> None:
    rubric = Rubric(
        name="t",
        criteria=(
            Criterion(
                name="correctness",
                description="",
                labels=(Label("good", "", 1.0), Label("bad", "", 0.0)),
            ),
        ),
    )
    text = 'Reasoning: the answer is correct.\n{"correctness": "good"}\n'
    out = parse_judge_response(text, rubric)
    assert out == {"correctness": "good"}


def test_parse_judge_response_picks_last_matching_object() -> None:
    rubric = Rubric(
        name="t",
        criteria=(
            Criterion(
                name="correctness",
                description="",
                labels=(Label("good", "", 1.0),),
            ),
        ),
    )
    # First JSON-looking object is unrelated; we should pick the one with our key.
    text = '{"unrelated": 1} … final answer: {"correctness": "good"}'
    assert parse_judge_response(text, rubric) == {"correctness": "good"}


def test_parse_judge_response_raises_when_missing() -> None:
    rubric = Rubric(
        name="t",
        criteria=(Criterion(name="x", description="", labels=(Label("y", "", 1.0),)),),
    )
    with pytest.raises(ValueError):
        parse_judge_response("no json here", rubric)
