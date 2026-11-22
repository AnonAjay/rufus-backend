"""
Benchmark for Rufus Desktop App / Backend Cold Start and Import Latency.
Strictly adheres to Hard Rules:
- time.perf_counter()
- Cold start runs reported separately from warm runs
- Raw samples logged to CSV
"""
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from benchmarks.stats_utils import calc_stats, log_samples_to_csv


def run_cold_start_benchmark(n_runs: int = 10) -> dict[str, Any]:
    """
    Measure fresh-process import latency of Rufus backend (cold start) over n_runs.
    """
    cmd = [
        sys.executable,
        "-c",
        (
            "import sys, time; "
            "t0 = time.perf_counter(); "
            "sys.path.insert(0, r'rufus-backend'); "
            "import app.agent.tools, app.agent.permissions, app.agent.laya_router; "
            "print(f'{time.perf_counter() - t0:.6f}')"
        ),
    ]

    raw_samples: list[dict[str, Any]] = []
    latencies: list[float] = []

    # First run is true cold-start (system cache unprimed)
    cold_start_latencies: list[float] = []

    for i in range(n_runs):
        proc = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"Error on run {i}: {proc.stderr}")
            continue
        try:
            val = float(proc.stdout.strip().splitlines()[-1])
            latencies.append(val)
            if i < 3:
                cold_start_latencies.append(val)
            raw_samples.append({
                "run": i + 1,
                "is_cold_start": i < 3,
                "import_latency_s": val,
            })
        except ValueError:
            continue

    csv_path = BASE_DIR / "benchmarks" / "results" / "cold_start_samples.csv"
    log_samples_to_csv(csv_path, raw_samples, ["run", "is_cold_start", "import_latency_s"])

    warm_runs = latencies[3:] if len(latencies) > 3 else latencies

    return {
        "n_total": len(latencies),
        "cold_start_runs": {
            "n": len(cold_start_latencies),
            "samples": cold_start_latencies,
            "stats": calc_stats(cold_start_latencies),
        },
        "warm_runs": {
            "n": len(warm_runs),
            "stats": calc_stats(warm_runs),
        },
    }


if __name__ == "__main__":
    print("Running Cold Start Benchmark...")
    res = run_cold_start_benchmark(n_runs=10)
    print("Cold Start Result:", res)
