"""Total Agreement Rate metrics — TARr@N (raw) and TARa@N (parsed answer).

From Atil et al. *Non-Determinism of "Deterministic" LLM Settings*::

    TARr@N = (# outputs equal to the modal raw output) / N
    TARa@N = (# parsed answers equal to the modal parsed answer) / N

Both are defined in ``[1/N, 1.0]``. ``1.0`` ⇒ the model is fully deterministic
across the N runs.

We use the **modal** (most-common) output as the reference, which Atil et al.
cite as the most defensible choice when the "true" answer is unknown. Callers
that prefer a fixed reference can pass ``reference=`` explicitly.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

T = TypeVar("T")


def _modal(outputs: Sequence[Any]) -> Any:
    """Return the most-frequent element (ties broken by first-seen order)."""
    counts = Counter(outputs)
    # Counter.most_common preserves insertion order for ties (Py 3.7+).
    return counts.most_common(1)[0][0]


def tar_r(outputs: Sequence[Any], reference: Any | None = None) -> float:
    """Total Agreement Rate over raw outputs (TARr@N).

    Parameters
    ----------
    outputs : Sequence[Any]
        N raw outputs (typically strings) from N runs of the same prompt.
    reference : Any, optional
        If provided, agreement is measured against this exact value. Otherwise
        the modal output is used (Atil et al. default).

    Returns
    -------
    float
        Fraction in ``[0.0, 1.0]``. Returns ``0.0`` for an empty input (caller
        almost certainly has a bug; we don't raise to keep the metric monotone).
    """
    n = len(outputs)
    if n == 0:
        return 0.0
    ref = reference if reference is not None else _modal(outputs)
    return sum(1 for out in outputs if out == ref) / n


def tar_a[T](
    outputs: Sequence[Any],
    parser: Callable[[Any], T],
    reference: T | None = None,
) -> float:
    """Total Agreement Rate over **parsed answers** (TARa@N).

    Parameters
    ----------
    outputs : Sequence[Any]
        N raw outputs to parse.
    parser : Callable[[Any], T]
        Function mapping each raw output to a canonical answer (e.g.
        extracting the boxed ``\\boxed{42}`` from a math response). Must be
        deterministic and total.
    reference : T, optional
        Optional fixed reference; otherwise modal parsed answer is used.

    Returns
    -------
    float
        Fraction in ``[0.0, 1.0]``.
    """
    n = len(outputs)
    if n == 0:
        return 0.0
    parsed = [parser(o) for o in outputs]
    ref = reference if reference is not None else _modal(parsed)
    return sum(1 for ans in parsed if ans == ref) / n
