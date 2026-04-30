"""Experiment 04: Inspect AI Task/Solver/Scorer composes with mockllm (research §2.2, §4.1).

Assumption: We can build a minimal Task with `mockllm/model` provider and
score samples with `match()` — proving the triad is wrappable as one RF keyword.
"""

import os

import inspect_ai
from inspect_ai import Task
from inspect_ai import eval as inspect_eval
from inspect_ai.dataset import Sample
from inspect_ai.scorer import match
from inspect_ai.solver import generate


def main() -> int:
    print("inspect_ai version:", inspect_ai.__version__)
    samples = [Sample(input="What is 2+2? Answer with just the number.", target="4")]
    task = Task(dataset=samples, solver=generate(), scorer=match())
    # mockllm/model produces a deterministic stub completion (configurable via env)
    os.environ.setdefault("INSPECT_EVAL_MODEL", "mockllm/model")
    try:
        logs = inspect_eval(task, model="mockllm/model", display="plain", log_dir="./_inspect_log")
    except Exception as e:
        print("eval failed:", type(e).__name__, e)
        print("FAIL exp_04_inspect_ai_task")
        return 1

    if not logs:
        print("FAIL exp_04_inspect_ai_task — no logs returned")
        return 1
    log = logs[0]
    has_samples = bool(getattr(log, "samples", None))
    sample0 = log.samples[0] if has_samples else None
    score = None
    if sample0 is not None:
        # samples may carry .scores dict or .score attribute depending on version
        score = getattr(sample0, "scores", None) or getattr(sample0, "score", None)
    print("status:", getattr(log, "status", "?"))
    print("n_samples:", len(log.samples) if has_samples else 0)
    print("first sample.score:", score)
    schema_ok = has_samples and (score is not None)
    print("PASS" if schema_ok else "PARTIAL", "exp_04_inspect_ai_task")
    return 0 if schema_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
