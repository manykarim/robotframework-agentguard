"""Experiment 06: scipy provides Mann-Whitney U + bootstrap CI (research §2.7, §3.4).

Assumption: scipy.stats.mannwhitneyu and scipy.stats.bootstrap deliver the test
statistics needed by the StatsLibrary, and we can compute Cliff's delta manually.
"""
import numpy as np
from scipy import stats


def cliffs_delta(x, y) -> float:
    nx, ny = len(x), len(y)
    gt = sum(1 for a in x for b in y if a > b)
    lt = sum(1 for a in x for b in y if a < b)
    return (gt - lt) / (nx * ny)


def main() -> int:
    rng = np.random.default_rng(42)
    a = rng.normal(loc=0.0, scale=1.0, size=30)
    b = rng.normal(loc=0.3, scale=1.0, size=30)

    u = stats.mannwhitneyu(b, a, alternative="greater")
    delta = cliffs_delta(b, a)
    res = stats.bootstrap((b,), np.mean, n_resamples=2000,
                          confidence_level=0.95, random_state=rng)
    ci_low, ci_high = res.confidence_interval.low, res.confidence_interval.high

    print("scipy version:", __import__("scipy").__version__)
    print(f"Mann-Whitney U: stat={u.statistic:.2f}  p={u.pvalue:.4g}")
    print(f"Cliff's delta : {delta:+.3f}")
    print(f"Bootstrap 95%CI for mean(b): [{ci_low:.3f}, {ci_high:.3f}]")

    # Sanity: with shift=0.3σ and n=30 we *can* fail to reject H0 — that's fine,
    # we only assert that the API surface returns the right shapes/types.
    ok = (
        isinstance(u.pvalue, float)
        and -1.0 <= delta <= 1.0
        and ci_low < ci_high
    )
    print("PASS" if ok else "FAIL", "exp_06_scipy_stats")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
