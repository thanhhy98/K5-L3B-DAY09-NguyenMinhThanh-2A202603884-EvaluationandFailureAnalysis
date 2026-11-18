"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
import math
from math import comb

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge labels must have equal length")
    tp = sum(h == POS and j == POS for h, j in zip(human, judge))
    fp = sum(h != POS and j == POS for h, j in zip(human, judge))
    fn = sum(h == POS and j != POS for h, j in zip(human, judge))
    tn = len(human) - tp - fp - fn
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    """Return precision and recall with FAIL as the positive class."""
    cm = confusion(human, judge)
    pden, rden = cm["tp"] + cm["fp"], cm["tp"] + cm["fn"]
    return (cm["tp"] / pden if pden else 0.0,
            cm["tp"] / rden if rden else 0.0)


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    if len(human) != len(judge):
        raise ValueError("human and judge labels must have equal length")
    n = len(human)
    if n == 0:
        raise ValueError("kappa is undefined for empty labels")
    labels = set(human) | set(judge)
    observed = sum(h == j for h, j in zip(human, judge)) / n
    expected = sum(sum(x == label for x in human) * sum(x == label for x in judge)
                   for label in labels) / (n * n)
    if math.isclose(expected, 1.0):
        raise ValueError("kappa is undefined when expected agreement is 1")
    return (observed - expected) / (1 - expected)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denom = sensitivity + specificity - 1
    if math.isclose(denom, 0.0):
        raise ValueError("sensitivity and specificity do not identify prevalence")
    return min(1.0, max(0.0, (observed_rate + specificity - 1) / denom))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    if len(a) != len(b) or not a:
        raise ValueError("paired samples must be non-empty and equal length")
    if n_resamples <= 0 or not 0 < confidence < 1:
        raise ValueError("invalid bootstrap parameters")
    if all(x == y for x, y in zip(a, b)):
        return (0.0, 0.0, 0.0)
    import numpy as np
    from scipy.stats import bootstrap
    result = bootstrap((np.asarray(a, dtype=float), np.asarray(b, dtype=float)),
                       statistic=lambda x, y, axis=-1: np.mean(x - y, axis=axis),
                       paired=True, vectorized=True, n_resamples=n_resamples,
                       confidence_level=confidence, method="percentile",
                       rng=np.random.default_rng(rng))
    return (float(np.mean(np.asarray(a) - np.asarray(b))),
            float(result.confidence_interval.low), float(result.confidence_interval.high))


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _validate_k(n, c, k)
    return 1.0 - (comb(n - c, k) / comb(n, k) if n - c >= k else 0.0)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _validate_k(n, c, k)
    return comb(c, k) / comb(n, k) if c >= k else 0.0


def _validate_k(n: int, c: int, k: int) -> None:
    if n < 0 or c < 0 or c > n or k < 1:
        raise ValueError("require n >= c >= 0 and k >= 1")
    if k > n:
        raise ValueError("k cannot exceed n")
