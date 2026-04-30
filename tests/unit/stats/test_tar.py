"""Total Agreement Rate primitives (Atil et al.) — TARr@N raw, TARa@N parsed."""

from __future__ import annotations

import pytest

from AgentGuard.stats.tar import tar_a, tar_r


class TestTarR:
    def test_perfect_agreement(self) -> None:
        assert tar_r(["yes"] * 10) == pytest.approx(1.0)

    def test_partial_agreement(self) -> None:
        # 4 of 5 outputs equal "yes" → modal "yes" at rate 0.8
        assert tar_r(["yes", "yes", "yes", "no", "yes"]) == pytest.approx(0.8)

    def test_explicit_reference(self) -> None:
        assert tar_r(["yes", "no", "no", "yes"], reference="yes") == pytest.approx(0.5)

    def test_empty_returns_zero(self) -> None:
        assert tar_r([]) == 0.0

    def test_singletons_each_count_one(self) -> None:
        # No two equal → modal is first ("a"), rate 1/5
        assert tar_r(["a", "b", "c", "d", "e"]) == pytest.approx(0.2)


class TestTarA:
    def test_with_parser(self) -> None:
        outputs = ["The answer is 42.", "Final: 42", "About 41 maybe", "42!"]
        parser = lambda s: "42" if "42" in s else "?"
        assert tar_a(outputs, parser=parser) == pytest.approx(0.75)

    def test_explicit_reference_parser(self) -> None:
        outputs = ["yes maybe", "yes", "no thanks", "yes"]
        parser = lambda s: "yes" if "yes" in s else "no"
        assert tar_a(outputs, parser=parser, reference="yes") == pytest.approx(0.75)

    def test_empty_returns_zero(self) -> None:
        assert tar_a([], parser=str) == 0.0

    def test_disagreement_low(self) -> None:
        outs = ["answer: 1", "answer: 2", "answer: 3", "answer: 4"]
        score = tar_a(outs, parser=lambda s: s.split(":")[-1].strip())
        # All distinct → modal is the first, rate 1/4 = 0.25
        assert score == pytest.approx(0.25)
