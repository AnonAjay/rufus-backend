"""
Statistics and metrics calculation utilities for Rufus benchmarks.
Strict adherence to Hard Rules:
- time.perf_counter()
- n, median, IQR, min, max, p95 (n>=20), p99 (n>=100)
- Wilson 95% CI for proportions
- Bootstrap 95% CI (10,000 resamples)
"""
import math
import csv
from pathlib import Path
from typing import Any

def calc_stats(samples: list[float]) -> dict[str, Any]:
    """Calculate summary statistics for continuous measurements."""
    n = len(samples)
    if n == 0:
        return {"n": 0, "median": None, "iqr": None, "min": None, "max": None}
    
    sorted_s = sorted(samples)
    
    def percentile(p: float) -> float:
        idx = p * (n - 1)
        lower = int(math.floor(idx))
        upper = int(math.ceil(idx))
        weight = idx - lower
        return sorted_s[lower] * (1 - weight) + sorted_s[upper] * weight

    med = percentile(0.50)
    q1 = percentile(0.25)
    q3 = percentile(0.75)
    iqr = q3 - q1
    min_val = sorted_s[0]
    max_val = sorted_s[-1]
    
    res = {
        "n": n,
        "median": med,
        "iqr": iqr,
        "min": min_val,
        "max": max_val,
    }
    
    if n >= 20:
        res["p95"] = percentile(0.95)
    if n >= 100:
        res["p99"] = percentile(0.99)
        
    return res

def wilson_score_interval(successes: int, total: int, z: float = 1.95996) -> tuple[float, float]:
    """Calculate Wilson 95% confidence interval for proportions."""
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1 + (z**2) / total
    center = (p + (z**2) / (2 * total)) / denom
    spread = (z / denom) * math.sqrt((p * (1 - p) / total) + (z**2) / (4 * total**2))
    return max(0.0, center - spread), min(1.0, center + spread)

def bootstrap_diff_ci(a: list[float], b: list[float], num_resamples: int = 10000) -> tuple[float, float]:
    """Bootstrap 95% CI for difference in medians (a - b) with 10,000 resamples."""
    import numpy as np
    if len(a) == 0 or len(b) == 0:
        return 0.0, 0.0
    
    a_arr = np.array(a)
    b_arr = np.array(b)
    
    diffs = []
    rng = np.random.default_rng(seed=42)
    for _ in range(num_resamples):
        sample_a = rng.choice(a_arr, size=len(a_arr), replace=True)
        sample_b = rng.choice(b_arr, size=len(b_arr), replace=True)
        diffs.append(np.median(sample_a) - np.median(sample_b))
        
    diffs.sort()
    lower_idx = int(0.025 * num_resamples)
    upper_idx = int(0.975 * num_resamples)
    return float(diffs[lower_idx]), float(diffs[upper_idx])

def write_csv(filepath: Path | str, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    """Save raw benchmark samples to disk."""
    p = Path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

log_samples_to_csv = write_csv

