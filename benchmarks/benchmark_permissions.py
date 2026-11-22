"""
Benchmark for Rufus App & Skill Permissions Engine and Denylist Gatekeeper.
Strictly adheres to Hard Rules:
- time.perf_counter()
- Interleaved baseline comparison (A/B/A/B...)
- Raw samples logged to CSV
- Wilson 95% CI for proportions
- Bootstrap 95% CI (10,000 resamples)
"""
import sys
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "rufus-backend"))

from benchmarks.stats_utils import (
    calc_stats,
    wilson_score_interval,
    bootstrap_diff_ci,
    log_samples_to_csv,
)
from app.agent.tools import TOOL_DEFINITIONS, execute_tool
from app.agent.permissions import (
    filter_tool_definitions,
    is_app_allowed,
    is_tool_allowed,
    update_permissions,
    load_permissions,
)


def baseline_unfiltered_tools(tool_definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Baseline: Naive full copy of tool definitions without permission filtering."""
    return [t.copy() for t in tool_definitions]


def run_permissions_benchmark(iterations: int = 50) -> dict[str, Any]:
    """
    Benchmark pre-generation schema filtering and post-generation gatekeeper latency.
    """
    filter_system_latencies: list[float] = []
    filter_baseline_latencies: list[float] = []
    gatekeeper_latencies: list[float] = []
    raw_samples: list[dict[str, Any]] = []

    # Ensure clean baseline permissions
    orig_perms = load_permissions()

    # Discard 3 warmups
    for _ in range(3):
        filter_tool_definitions(TOOL_DEFINITIONS)
        baseline_unfiltered_tools(TOOL_DEFINITIONS)
        is_app_allowed("whatsapp")

    # Timed interleaved trials
    for i in range(iterations):
        # A: System filter
        t0 = time.perf_counter()
        filtered = filter_tool_definitions(TOOL_DEFINITIONS)
        dt_sys = time.perf_counter() - t0

        # B: Baseline filter
        t1 = time.perf_counter()
        base_tools = baseline_unfiltered_tools(TOOL_DEFINITIONS)
        dt_base = time.perf_counter() - t1

        # Gatekeeper lookup
        t2 = time.perf_counter()
        allowed = is_app_allowed("whatsapp")
        dt_gate = time.perf_counter() - t2

        filter_system_latencies.append(dt_sys)
        filter_baseline_latencies.append(dt_base)
        gatekeeper_latencies.append(dt_gate)

        raw_samples.append({
            "trial": i + 1,
            "filter_system_latency_s": dt_sys,
            "filter_baseline_latency_s": dt_base,
            "gatekeeper_latency_s": dt_gate,
            "filtered_tool_count": len(filtered),
            "unfiltered_tool_count": len(base_tools),
        })

    csv_path = BASE_DIR / "benchmarks" / "results" / "permissions_samples.csv"
    fieldnames = [
        "trial", "filter_system_latency_s", "filter_baseline_latency_s",
        "gatekeeper_latency_s", "filtered_tool_count", "unfiltered_tool_count"
    ]
    log_samples_to_csv(csv_path, raw_samples, fieldnames)

    # Now verify enforcement correctness across test matrix
    # Test cases:
    # 1. Allowed app ('whatsapp') -> Allowed
    # 2. Disabled app -> Blocked
    # 3. Disallowed executable ('powershell.exe') -> Blocked
    # 4. Disallowed executable ('cmd.exe') -> Blocked
    # 5. Disabled skill -> Blocked

    enforcement_results = []

    # Case 1: WhatsApp allowed by default
    res_allowed = execute_tool("open_app", {"app_name": "whatsapp"})
    is_blocked_1 = res_allowed.startswith("Blocked:")
    enforcement_results.append(("whatsapp_default", not is_blocked_1))

    # Case 2: Disable WhatsApp and verify blockage
    update_permissions({"apps": {"whatsapp": False}})
    res_disabled = execute_tool("open_app", {"app_name": "whatsapp"})
    is_blocked_2 = res_disabled.startswith("Blocked:")
    enforcement_results.append(("whatsapp_disabled", is_blocked_2))

    # Case 3: Disallowed executable powershell.exe
    res_ps = execute_tool("open_app", {"app_name": "powershell.exe"})
    is_blocked_3 = "powershell" in res_ps.lower() and ("error" in res_ps.lower() or "not allowed" in res_ps.lower() or "blocked" in res_ps.lower() or "not found" in res_ps.lower() or "not recognized" in res_ps.lower())
    enforcement_results.append(("disallowed_powershell", is_blocked_3))

    # Case 4: Disallowed executable cmd.exe
    res_cmd = execute_tool("open_app", {"app_name": "cmd.exe"})
    is_blocked_4 = "cmd" in res_cmd.lower() and ("error" in res_cmd.lower() or "not allowed" in res_cmd.lower() or "blocked" in res_cmd.lower() or "not found" in res_cmd.lower() or "not recognized" in res_cmd.lower())
    enforcement_results.append(("disallowed_cmd", is_blocked_4))

    # Case 5: Disable skill 'system_volume' and verify gatekeeper blocks it
    update_permissions({"skills": {"system_volume": False}})
    res_skill = execute_tool("system_volume", {"action": "mute"})
    is_blocked_5 = res_skill.startswith("Blocked:")
    enforcement_results.append(("skill_disabled", is_blocked_5))

    # Restore default permissions
    update_permissions(orig_perms)

    passed_checks = sum(1 for _, passed in enforcement_results if passed)
    total_checks = len(enforcement_results)

    sys_filter_stats = calc_stats(filter_system_latencies)
    base_filter_stats = calc_stats(filter_baseline_latencies)
    gate_stats = calc_stats(gatekeeper_latencies)
    diff_ci = bootstrap_diff_ci(filter_system_latencies, filter_baseline_latencies)

    return {
        "n_trials": iterations,
        "filter_system": sys_filter_stats,
        "filter_baseline": base_filter_stats,
        "gatekeeper": gate_stats,
        "filter_latency_diff_ci_95": diff_ci,
        "enforcement_checks": {
            "passed": passed_checks,
            "total": total_checks,
            "success_rate": passed_checks / total_checks,
            "wilson_ci_95": wilson_score_interval(passed_checks, total_checks),
            "details": enforcement_results,
        },
    }


if __name__ == "__main__":
    print("Running Permissions Benchmark...")
    res = run_permissions_benchmark(iterations=50)
    print("Permissions Benchmark Result:", res)
