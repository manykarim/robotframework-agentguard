"""HumanEval pass@k (research §3.4).

Numerically stable form (Chen et al. 2021, *Evaluating Large Language Models
Trained on Code*)::

    pass@k = 1 − C(n−c, k) / C(n, k)
           = 1 − Π_{i=0..k-1} (n − c − i) / (n − i)

The product form avoids the combinatorial overflow that arises for n ≫ k.
Falls back to ``0.0`` when ``c == 0`` and to ``1.0`` when ``c >= n − k + 1``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Union

# A flat list of bool means "n problems, each with one outcome — there is no
# way to compute pass@k>1 from that".  A list-of-lists means "n problems, each
# with up to m_i samples"; we then use HumanEval pass@k per problem and
# average across problems (the canonical aggregation).
Outcomes = Union[Sequence[bool], Sequence[Sequence[bool]]]


def _pass_at_k_single(n: int, c: int, k: int) -> float:
    """HumanEval pass@k for a single problem with `n` samples and `c` correct."""
    if k <= 0:
        raise ValueError(f"k must be >= 1; got {k!r}.")
    if n <= 0:
        raise ValueError(f"n must be >= 1; got {n!r}.")
    if k > n:
        raise ValueError(f"k ({k}) cannot exceed the number of samples per problem (n={n}).")
    if c <= 0:
        return 0.0
    if c >= n - k + 1:
        return 1.0
    # Product form: 1 - Π (n-c-i)/(n-i) for i in 0..k-1
    prob_all_fail = 1.0
    for i in range(k):
        prob_all_fail *= (n - c - i) / (n - i)
    return 1.0 - prob_all_fail


def pass_at_k(outcomes: Outcomes, k: int) -> float:
    """Compute pass@k over `outcomes`.

    Two accepted shapes:

    * **Flat** ``list[bool]`` — treated as one problem with ``n = len(outcomes)``
      samples and ``c = sum(outcomes)`` correct.
    * **Nested** ``list[list[bool]]`` — one inner list per problem; we compute
      pass@k per problem (allowing different ``n_i`` per problem) and return
      the unweighted mean (HumanEval convention).

    Parameters
    ----------
    outcomes : Outcomes
        See above.
    k : int
        Sampling budget (must satisfy ``1 <= k <= min n_i``).

    Returns
    -------
    float
        pass@k in ``[0.0, 1.0]``.
    """
    if isinstance(outcomes, Sequence) and len(outcomes) > 0 and isinstance(outcomes[0], (list, tuple)):
        nested: Iterable[Sequence[bool]] = outcomes  # type: ignore[assignment]
        per_problem = [_pass_at_k_single(n=len(samples), c=sum(1 for s in samples if s), k=k) for samples in nested]
        if not per_problem:
            return 0.0
        return sum(per_problem) / len(per_problem)

    flat: Sequence[bool] = outcomes  # type: ignore[assignment]
    return _pass_at_k_single(n=len(flat), c=sum(1 for s in flat if s), k=k)
