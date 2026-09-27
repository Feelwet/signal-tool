"""Transparent anomaly statistics: robust z-scores of a recent window vs the series' own baseline."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd


def robust_z(s: pd.Series, recent_n: int = 1, baseline_n: int = 60, min_baseline: int = 14) -> tuple[float, dict]:
    """z = (mean(last recent_n) - median(baseline)) / (1.4826 * MAD(baseline)).

    Baseline = the `baseline_n` observations immediately before the recent window.
    Falls back to the standard deviation if MAD is zero; returns NaN if baseline too short.
    """
    s = pd.Series(s).dropna()
    if len(s) < recent_n + min_baseline:
        return float("nan"), {"n_baseline": max(0, len(s) - recent_n)}
    recent = s.iloc[-recent_n:].mean()
    base = s.iloc[-(recent_n + baseline_n):-recent_n]
    med = base.median()
    scale = 1.4826 * (base - med).abs().median()
    if not scale or scale < 1e-12:
        scale = base.std()
    if not scale or scale < 1e-12 or math.isnan(scale):
        return float("nan"), {"n_baseline": len(base)}
    return float((recent - med) / scale), {"recent": float(recent), "baseline_median": float(med),
                                           "n_baseline": int(len(base))}


def clip(z: float, lo: float = -3, hi: float = 5) -> float:
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return float("nan")
    return float(max(lo, min(hi, z)))


def weighted_positive_score(components: dict[str, dict]) -> float:
    """Weighted mean of positive-clipped component scores over the components that have data.
    Components: {name: {"score": float|nan, "weight": float}}. Result on a 0-5 scale."""
    num = den = 0.0
    for c in components.values():
        v = c.get("score")
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        num += c["weight"] * max(0.0, min(5.0, v))
        den += c["weight"]
    return round(num / den, 3) if den else 0.0
