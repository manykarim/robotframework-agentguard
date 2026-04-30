"""Prompt builders + judge-response parsers extracted from ``library.py``."""

from __future__ import annotations

import json
import re
import statistics

from AgentGuard.judge.rubric import Criterion, Label, Rubric

PAIRWISE_LABELS: tuple[str, ...] = ("A", "B", "TIE")


def score_from_labels(labels: dict[str, str], rubric: Rubric) -> float:
    """Aggregate per-criterion label scores → mean ∈ [0, 1]."""
    if not rubric.criteria:
        return 0.0
    scores: list[float] = []
    for criterion in rubric.criteria:
        chosen = labels.get(criterion.name)
        if chosen is None:
            scores.append(0.0)
            continue
        lbl = criterion.label_for(chosen)
        scores.append(lbl.score if lbl is not None else 0.0)
    return statistics.fmean(scores)


def build_pairwise_prompt(a: str, b: str, rubric: Rubric) -> str:
    """Build the pairwise-comparison judge prompt."""
    criteria_block = "\n".join(f"- {c.name}: {c.description}" for c in rubric.criteria)
    return (
        "You are an impartial pairwise judge. Compare RESPONSE_A and RESPONSE_B "
        "against the rubric below; reason briefly, then on the LAST line output "
        'a single JSON object: {"winner": "A" | "B" | "TIE"}.\n\n'
        f"Rubric: {rubric.name or '(unnamed)'}\n"
        f"{criteria_block}\n\n"
        f'RESPONSE_A:\n"""\n{a}\n"""\n\n'
        f'RESPONSE_B:\n"""\n{b}\n"""'
    )


def extract_pairwise_winner(text: str) -> str:
    """Pull ``"A" | "B" | "TIE"`` from a pairwise judge response."""
    for match in re.finditer(r"\{[^{}]*\}", text, flags=re.DOTALL):
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        winner = str(obj.get("winner", "")).strip().upper()
        if winner in PAIRWISE_LABELS:
            return winner
    upper = text.strip().upper()
    for label in PAIRWISE_LABELS:
        if upper.endswith(label):
            return label
    raise ValueError(f"Could not extract pairwise winner from response: {text!r}")


def default_equivalence_rubric() -> Rubric:
    """Default rubric for ``Tool Output Should Be Semantically Equal``."""
    return Rubric(
        name="semantic-equivalence",
        criteria=(
            Criterion(
                name="equivalence",
                description="Does the actual output convey the same meaning as the reference?",
                labels=(
                    Label("equivalent", "matches the reference within paraphrase tolerance", 1.0),
                    Label("partial", "missing a non-essential detail", 0.5),
                    Label("not-equivalent", "contradicts or omits an essential detail", 0.0),
                ),
            ),
        ),
    )
