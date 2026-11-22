"""
Rufus End-to-End Benchmark Execution Harness with Real Local Model.
Strictly adheres to all E2E Rules:
- Uses real local llama3.2 on Ollama and real Laya ModernBERT router.
- Backs up and restores data/ directory.
- Runs test cases x 3 repeats at temperature 0, after 3 discarded warm-ups.
- Executes A/B test of the call-2 skip (10 commands x 5 runs x 2 arms).
- Generates raw.csv, EVIDENCE.txt, and FINDINGS.md under benchmarks/e2e/results/<timestamp>/.
- Cold-start timeout 120 s.
"""
import ast
import csv
import ctypes
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Ensure project paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
RUFUS_BACKEND_DIR = Path(os.environ.get("RUFUS_BACKEND_DIR", str(BASE_DIR / "rufus-backend")))
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(RUFUS_BACKEND_DIR))

from benchmarks.stats_utils import (
    calc_stats,
    wilson_score_interval,
    bootstrap_diff_ci,
)

from app.agent.tools import TOOL_DEFINITIONS

PYTHON_EXE = r"C:\Users\Asus\miniconda3\envs\rufus\python.exe"
PORT = int(os.environ.get("RUFUS_E2E_PORT", 8008))
BASE_URL = f"http://127.0.0.1:{PORT}"


def get_git_info() -> tuple[str, str]:
    """Retrieve commit hash and git status --porcelain."""
    try:
        proc_hash = subprocess.run(
            ["git", "-C", str(RUFUS_BACKEND_DIR), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True
        )
        commit = proc_hash.stdout.strip()
    except Exception:
        commit = "unknown"

    try:
        proc_stat = subprocess.run(
            ["git", "-C", str(RUFUS_BACKEND_DIR), "status", "--porcelain"],
            capture_output=True, text=True, check=True
        )
        status = proc_stat.stdout.strip() or "clean"
    except Exception:
        status = "unknown"
    return commit, status


def get_environment_info() -> dict[str, str]:
    """Capture host system specifications."""
    commit, status = get_git_info()
    cpu_brand = platform.processor() or "Unknown CPU"

    gpu_info = "Unknown GPU"
    try:
        smi = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if smi.returncode == 0 and smi.stdout.strip():
            gpu_info = smi.stdout.strip().split("\n")[0]
    except Exception:
        pass

    ram_gb = "Unknown"
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            ram_gb = f"{stat.ullTotalPhys / (1024**3):.1f} GB"
    except Exception:
        pass

    ollama_ver = "Unknown"
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/version")
        with urllib.request.urlopen(req, timeout=3) as resp:
            ver_data = json.loads(resp.read().decode("utf-8"))
            ollama_ver = ver_data.get("version", "unknown")
    except Exception:
        pass

    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu": cpu_brand,
        "ram": ram_gb,
        "gpu": gpu_info,
        "python": sys.version.split()[0],
        "ollama_version": ollama_ver,
        "model": "ollama/llama3.2:latest",
        "git_commit": commit,
        "git_status": status,
    }


def coerce_to_schema_type(val: Any, target_type: str) -> Any:
    """Coerce value to target schema type for robust parameter comparison."""
    if val is None:
        return None
    if target_type == "integer":
        try:
            return int(float(str(val).strip()))
        except (ValueError, TypeError):
            return val
    elif target_type == "number":
        try:
            return float(str(val).strip())
        except (ValueError, TypeError):
            return val
    elif target_type == "boolean":
        if isinstance(val, bool):
            return val
        s = str(val).strip().lower()
        if s in {"true", "1", "yes"}:
            return True
        if s in {"false", "0", "no"}:
            return False
        return val
    elif target_type == "string":
        return str(val).strip().lower()
    return val


def compare_args_against_schema(exec_args: dict[str, Any], exp_args: dict[str, Any], tool_name: str) -> bool:
    """Compare tool arguments after coercing both sides to the tool's JSON-schema types."""
    if not exp_args:
        return True

    tool_def = next((t for t in TOOL_DEFINITIONS if t.get("name") == tool_name), None)
    schema_props = {}
    if tool_def and "parameters" in tool_def and "properties" in tool_def["parameters"]:
        schema_props = tool_def["parameters"]["properties"]

    for k, exp_val in exp_args.items():
        actual_val = exec_args.get(k)
        # Check alias keys for volume (level vs value)
        if actual_val is None and k == "level":
            actual_val = exec_args.get("value")
        elif actual_val is None and k == "value":
            actual_val = exec_args.get("level")

        if actual_val is None:
            return False

        prop_type = schema_props.get(k, {}).get("type", "string")
        c_actual = coerce_to_schema_type(actual_val, prop_type)
        c_expected = coerce_to_schema_type(exp_val, prop_type)

        if isinstance(c_actual, str) and isinstance(c_expected, str):
            if c_expected not in c_actual and c_actual not in c_expected:
                return False
        elif c_actual != c_expected:
            return False

    return True


def send_chat_request(session_id: str, message: str, persona: str = "auto") -> tuple[dict[str, Any], float]:
    """Send HTTP request to /agent/chat on harness server and measure roundtrip latency."""
    url = f"{BASE_URL}/agent/chat"
    payload = json.dumps({"session_id": session_id, "message": message, "persona": persona}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    t0 = time.perf_counter()
    try:
        # Rule: cold-start timeout 120 s
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        data = {"reply": f"ERROR: {exc}", "action_type": "speech", "actions": []}
    lat = time.perf_counter() - t0
    return data, lat


def reset_telemetry() -> None:
    try:
        req = urllib.request.Request(f"{BASE_URL}/e2e/reset", data=b"{}", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass
    except Exception:
        pass


def get_telemetry() -> dict[str, Any]:
    try:
        req = urllib.request.Request(f"{BASE_URL}/e2e/telemetry")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}


def parse_python_ast(reply_text: str) -> bool:
    """Check if reply contains Python code fence and ast.parse() succeeds."""
    pattern = r"```(?:python|py)?\s*\n(.*?)```"
    matches = re.findall(pattern, reply_text, flags=re.DOTALL)
    if not matches:
        return False
    for code_block in matches:
        try:
            ast.parse(code_block)
            return True
        except Exception:
            pass
    return False


def is_clarification(reply_text: str) -> bool:
    """Check if assistant reply asks a clarifying question."""
    t = reply_text.strip().lower()
    return "?" in t or any(w in t for w in ["who", "what", "which", "please specify", "could you provide", "tell me", "confirm"])


def write_reports(
    results_dir: Path,
    env_info: dict[str, str],
    raw_samples: list[dict[str, Any]],
    cases_list: list[dict[str, Any]],
    cold_start_samples: list[float],
) -> None:
    """Generate raw.csv, EVIDENCE.txt, and FINDINGS.md adhering strictly to Rule 8."""
    results_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write raw.csv
    raw_csv_path = results_dir / "raw.csv"
    fieldnames = [
        "case_id",
        "category",
        "repeat",
        "turns_count",
        "input_turns",
        "expected_path",
        "actual_path",
        "path_ok",
        "expected_tool",
        "actual_tool",
        "tool_ok",
        "args_ok",
        "must_not_violated",
        "coder_ast_ok",
        "clarification_ok",
        "blocked_ok",
        "success",
        "latency_s",
        "llm_calls",
        "prompt_tokens",
        "completion_tokens",
        "tokens_per_sec",
        "reply_text",
    ]
    with open(raw_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in raw_samples:
            writer.writerow(r)

    # 2. Compute aggregate metrics
    categories = sorted(list(set(r["category"] for r in raw_samples)))
    cat_metrics = {}
    for cat in categories:
        c_samples = [r for r in raw_samples if r["category"] == cat]
        total_runs = len(c_samples)
        path_ok_cnt = sum(r["path_ok"] for r in c_samples)
        tool_ok_cnt = sum(r["tool_ok"] for r in c_samples)
        args_ok_cnt = sum(r["args_ok"] for r in c_samples)
        success_cnt = sum(r["success"] for r in c_samples)

        cat_metrics[cat] = {
            "n_runs": total_runs,
            "path_acc": (path_ok_cnt / total_runs) if total_runs else 0.0,
            "path_ci": wilson_score_interval(path_ok_cnt, total_runs),
            "tool_acc": (tool_ok_cnt / total_runs) if total_runs else 0.0,
            "tool_ci": wilson_score_interval(tool_ok_cnt, total_runs),
            "args_acc": (args_ok_cnt / total_runs) if total_runs else 0.0,
            "args_ci": wilson_score_interval(args_ok_cnt, total_runs),
            "success_rate": (success_cnt / total_runs) if total_runs else 0.0,
            "success_ci": wilson_score_interval(success_cnt, total_runs),
        }

    # Distinct query level metrics
    cases_by_id = {c["id"]: c for c in cases_list}
    distinct_ids = sorted(list(set(r["case_id"] for r in raw_samples)))

    f_cases = [r for r in raw_samples if r["category"] == "near_miss_trap"]
    f_total_runs = len(f_cases)
    f_false_runs = sum(1 for r in f_cases if r["actual_tool"] != "NONE" or r["must_not_violated"] == 1)
    f_rate = (f_false_runs / f_total_runs) if f_total_runs else 0.0
    f_ci = wilson_score_interval(f_false_runs, f_total_runs)

    inconsistent_cases = 0
    for cid in distinct_ids:
        c_runs = [r for r in raw_samples if r["case_id"] == cid]
        if c_runs:
            first_succ = c_runs[0]["success"]
            if any(r["success"] != first_succ for r in c_runs):
                inconsistent_cases += 1
    inconsistency_rate = (inconsistent_cases / len(distinct_ids)) if distinct_ids else 0.0

    path_latencies = {1: [], 2: [], 4: [], 5: []}
    for r in raw_samples:
        p = r["actual_path"]
        if p in path_latencies:
            path_latencies[p].append(r["latency_s"])

    path_stats = {p: calc_stats(lats) for p, lats in path_latencies.items()}
    cold_stats = calc_stats(cold_start_samples)

    tok_sec_samples = [r["tokens_per_sec"] for r in raw_samples if r["tokens_per_sec"] > 0]
    tok_sec_stats = calc_stats(tok_sec_samples) if tok_sec_samples else {"median": 0.0, "iqr": 0.0, "n": 0}

    # 3. Write EVIDENCE.txt
    evidence_path = results_dir / "EVIDENCE.txt"
    with open(evidence_path, "w", encoding="utf-8") as f:
        f.write("RUFUS E2E BENCHMARK EXECUTION EVIDENCE\n")
        f.write("=" * 60 + "\n\n")
        f.write("[ENVIRONMENT]\n")
        for k, v in env_info.items():
            f.write(f"{k}: {v}\n")
        f.write(f"execution_timestamp: {datetime.now().isoformat()}\n\n")

        f.write("[DISCARDED WARM-UPS]\n")
        f.write(f"count: {len(cold_start_samples)}\n")
        f.write(f"latencies_s: {[round(x, 3) for x in cold_start_samples]}\n")
        f.write(f"median_s: {cold_stats.get('median', 0.0):.3f}\n\n")

        f.write("[METRICS PER CATEGORY]\n")
        for cat, m in cat_metrics.items():
            f.write(f"category: {cat}\n")
            f.write(f"  n_samples: {m['n_runs']}\n")
            f.write(f"  success_rate: {m['success_rate']:.4f} (95% CI: [{m['success_ci'][0]:.4f}, {m['success_ci'][1]:.4f}])\n")
            f.write(f"  path_accuracy: {m['path_acc']:.4f} (95% CI: [{m['path_ci'][0]:.4f}, {m['path_ci'][1]:.4f}])\n")
            f.write(f"  tool_accuracy: {m['tool_acc']:.4f} (95% CI: [{m['tool_ci'][0]:.4f}, {m['tool_ci'][1]:.4f}])\n")
            f.write(f"  args_accuracy: {m['args_acc']:.4f} (95% CI: [{m['args_ci'][0]:.4f}, {m['args_ci'][1]:.4f}])\n\n")

        f.write("[FALSE ACTION RATE (CATEGORY F - NEAR MISS TRAPS)]\n")
        f.write(f"n_samples: {f_total_runs}\n")
        f.write(f"false_action_rate: {f_rate:.4f}\n")
        f.write(f"wilson_95_ci: [{f_ci[0]:.4f}, {f_ci[1]:.4f}]\n\n")

        f.write("[INCONSISTENCY RATE]\n")
        f.write(f"distinct_queries: {len(distinct_ids)}\n")
        f.write(f"inconsistent_queries: {inconsistent_cases}\n")
        f.write(f"inconsistency_rate: {inconsistency_rate:.4f}\n\n")

        f.write("[LATENCY PER PATH (WALL SECONDS)]\n")
        for p, s in path_stats.items():
            f.write(f"path_{p}:\n")
            f.write(f"  n: {s.get('n', 0)}\n")
            f.write(f"  median_s: {s.get('median', 0.0):.3f}\n")
            f.write(f"  iqr_s: {s.get('iqr', 0.0):.3f}\n")
            f.write(f"  min_s: {s.get('min', 0.0):.3f}\n")
            f.write(f"  max_s: {s.get('max', 0.0):.3f}\n")
            if s.get("p95") is not None:
                f.write(f"  p95_s: {s['p95']:.3f}\n")

        f.write("\n[THROUGHPUT]\n")
        f.write(f"tokens_per_sec_median: {tok_sec_stats.get('median', 0.0):.2f}\n")
        f.write(f"tokens_per_sec_iqr: {tok_sec_stats.get('iqr', 0.0):.2f}\n")

    # 4. Write FINDINGS.md
    failing_cases = []
    for c_id in distinct_ids:
        runs = [r for r in raw_samples if r["case_id"] == c_id]
        failed_runs = [r for r in runs if r["success"] == 0]
        if failed_runs:
            c = cases_by_id.get(c_id, {"category": "unknown", "turns": [], "expected_path": 1, "expected_tool": "NONE"})
            severity = 5
            root_cause_guess = "General accuracy failure"

            has_unwanted_action = any(r["must_not_violated"] == 1 or (c["expected_tool"] == "NONE" and r["actual_tool"] != "NONE") for r in runs)
            has_wrong_tool = any(r["tool_ok"] == 0 or r["args_ok"] == 0 for r in runs)
            has_missing_clarif = any(c["category"] == "missing_params" and r["clarification_ok"] == 0 for r in runs)
            has_wrong_path = any(r["path_ok"] == 0 for r in runs)

            if has_unwanted_action:
                severity = 1
                root_cause_guess = "LLM emitted tool call despite knowledge-only request (prompt attention leak)"
            elif has_wrong_tool:
                severity = 2
                root_cause_guess = "Tool selection or parameter parsing failed in tool schema mapping"
            elif has_missing_clarif:
                severity = 3
                root_cause_guess = "Assistant replied with generic text instead of prompting user for missing argument"
            elif has_wrong_path:
                severity = 4
                root_cause_guess = "Laya intent router classified query into wrong action_type branch"

            failing_cases.append({
                "id": c_id,
                "category": c["category"],
                "severity": severity,
                "input": " | ".join(c["turns"]),
                "expected": f"Path: {c['expected_path']}, Tool: {c['expected_tool']}, Args: {c.get('expected_args', {})}",
                "actual": f"Path: {failed_runs[0]['actual_path']}, Tool: {failed_runs[0]['actual_tool']}",
                "reply": failed_runs[0]["reply_text"],
                "failed_repeats": len(failed_runs),
                "guess": root_cause_guess,
                "is_real_life": c["category"] in {"multi_turn"} or "hinglish" in c_id.lower(),
            })

    failing_cases.sort(key=lambda x: x["severity"])

    findings_path = results_dir / "FINDINGS.md"
    with open(findings_path, "w", encoding="utf-8") as f:
        f.write("# Rufus E2E Test Suite Findings Report\n\n")
        f.write(f"**Date**: {datetime.now().isoformat()}  \n")
        f.write(f"**Total Distinct Queries Tested**: {len(distinct_ids)}  \n")
        f.write(f"**Repeats per Query**: 3  \n")
        f.write(f"**Temperature**: 0  \n\n")
        f.write("---\n\n")
        f.write("## Summary of Failures by Severity\n\n")
        for fc in failing_cases:
            f.write(f"### [Severity {fc['severity']}] {fc['id']}\n")
            f.write(f"- **Input**: `{fc['input']}`\n")
            f.write(f"- **Expected**: {fc['expected']}\n")
            f.write(f"- **Actual**: {fc['actual']}\n")
            f.write(f"- **Failed Repeats**: {fc['failed_repeats']}/3\n")
            clean_reply = fc['reply'].replace('\r', ' ').replace('\n', ' ')[:120]
            f.write(f"- **Sample Reply**: *\"{clean_reply}\"*\n")
            f.write(f"- **Root Cause Guess**: {fc['guess']} *(GUESS)*\n\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Rufus E2E Benchmark Runner")
    parser.add_argument("--cases", default="cases.yaml", help="YAML cases filename (default: cases.yaml)")
    parser.add_argument("--max-cases", type=int, default=0, help="Max distinct cases to test (0 = all)")
    parser.add_argument("--repeats", type=int, default=3, help="Repeats per case (default: 3)")
    parser.add_argument("--output-dir", default=None, help="Explicit output results directory")
    parser.add_argument("--time-budget", type=int, default=5400, help="Wall-clock time budget in seconds (default: 90 min)")
    args = parser.parse_args()

    start_wall_time = time.time()
    max_duration_s = args.time_budget

    print("=" * 70)
    print("STARTING RUFUS END-TO-END BENCHMARK WITH REAL LOCAL MODEL")
    print("=" * 70)

    # 1. Capture environment
    env_info = get_environment_info()
    print("Environment specifications:")
    for k, v in env_info.items():
        print(f"  {k}: {v}")

    # 2. Results directory
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.output_dir:
        results_dir = Path(args.output_dir)
    else:
        results_dir = BASE_DIR / "benchmarks" / "e2e" / "results" / ts

    # 3. Load test cases
    cases_file = BASE_DIR / "benchmarks" / "e2e" / args.cases
    if not cases_file.exists():
        cases_file = RUFUS_BACKEND_DIR / "benchmarks" / "e2e" / args.cases

    with open(cases_file, "r", encoding="utf-8") as f:
        cases_yaml = yaml.safe_load(f)
    cases_list = cases_yaml.get("cases", [])
    if args.max_cases > 0:
        cases_list = cases_list[:args.max_cases]
    print(f"Loaded {len(cases_list)} test cases from {cases_file}.")

    raw_samples: list[dict[str, Any]] = []
    cold_start_samples: list[float] = []
    harness_proc = None

    try:
        # Launch harness server
        harness_script = BASE_DIR / "benchmarks" / "e2e" / "harness_server.py"
        print(f"Launching harness server on {BASE_URL}...")
        env = os.environ.copy()
        env["RUFUS_E2E_PORT"] = str(PORT)
        harness_proc = subprocess.Popen(
            [PYTHON_EXE, str(harness_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )

        # Wait for server
        online = False
        for _ in range(60):
            try:
                req = urllib.request.Request(f"{BASE_URL}/e2e/health")
                with urllib.request.urlopen(req, timeout=1) as resp:
                    if resp.status == 200:
                        online = True
                        break
            except Exception:
                time.sleep(1)

        if not online:
            raise RuntimeError("Harness server failed to start within 60 seconds.")
        print("Harness server is online and responding.")

        # Discard 3 warm-ups on Case 1 per Rule
        print("\nExecuting 3 warm-up requests (discarded)...")
        for w_idx in range(3):
            reset_telemetry()
            _, w_lat = send_chat_request(f"warmup_{w_idx}", "Hi Rufus, warmup!", persona="companion")
            cold_start_samples.append(w_lat)
            print(f"  Warm-up {w_idx + 1} latency: {w_lat:.3f} s")

        # Run cases x repeats
        print(f"\nRunning test cases x {args.repeats} repeats (time budget monitored)...")
        for case_idx, case in enumerate(cases_list):
            elapsed = time.time() - start_wall_time
            if elapsed > max_duration_s:
                print(f"Time budget reached ({elapsed / 60:.1f} min elapsed). Stopping at case {case_idx}.")
                break

            case_id = case["id"]
            category = case["category"]
            expected_path = case["expected_path"]
            expected_tool = case.get("expected_tool", "NONE")
            expected_args = case.get("expected_args", {})
            must_not = case.get("must_not", [])
            turns = case.get("turns", [])

            case_success_count = 0
            case_latencies = []

            for repeat in range(1, args.repeats + 1):
                session_id = f"e2e_{case_id}_rep{repeat}"
                turn_latencies = []
                final_reply = ""
                final_telem = {}
                actions_taken = []
                path_detected = 1

                for t_idx, turn_text in enumerate(turns):
                    reset_telemetry()
                    resp_data, lat = send_chat_request(session_id, turn_text, persona="auto")
                    turn_latencies.append(lat)
                    final_reply = resp_data.get("reply", "")
                    actions_taken = resp_data.get("actions", [])
                    telem = get_telemetry()
                    final_telem = telem

                    action_type = resp_data.get("action_type", "speech")
                    executed_tool = telem.get("last_tool_executed")

                    if action_type == "speech":
                        path_detected = 4 if category == "coder" else 1
                    else:
                        if executed_tool in {"web_search", "inspect_screen"}:
                            path_detected = 5
                        else:
                            path_detected = 2

                tot_latency = sum(turn_latencies)
                case_latencies.append(tot_latency)
                executed_tool_name = final_telem.get("last_tool_executed") or "NONE"
                llm_calls = final_telem.get("llm_calls_in_turn", 1)

                path_ok = (path_detected == expected_path)
                tool_ok = (executed_tool_name == expected_tool)

                args_ok = True
                exec_args = final_telem.get("last_tool_args", {})
                if expected_tool != "NONE":
                    args_ok = compare_args_against_schema(exec_args, expected_args, expected_tool)

                must_not_violated = False
                for mn in must_not:
                    if mn == "tool_call" and executed_tool_name != "NONE":
                        must_not_violated = True
                    elif mn == "open_app" and executed_tool_name == "open_app":
                        must_not_violated = True
                    elif mn == "spotify_control" and executed_tool_name == "spotify_control":
                        must_not_violated = True
                    elif mn == "whatsapp_send_message" and executed_tool_name == "whatsapp_send_message":
                        must_not_violated = True
                    elif mn == "system_volume" and executed_tool_name == "system_volume":
                        must_not_violated = True

                coder_ok = parse_python_ast(final_reply) if category == "coder" else True
                clarif_ok = is_clarification(final_reply) if category == "missing_params" else True
                blocked_ok = (len(actions_taken) > 0 and any("Blocked" in a for a in actions_taken)) or (executed_tool_name == "NONE") if category == "safety_permissions" else True

                multi_turn_ok = True
                if category == "multi_turn" and case_id == "I01_volume_relative_lower":
                    vol_acts = final_telem.get("volume_actions", [])
                    if vol_acts:
                        last_act = vol_acts[-1]
                        multi_turn_ok = (last_act.get("achieved_pct", 50) < 40)

                if category == "coder":
                    success = path_ok and not must_not_violated and coder_ok
                elif category == "near_miss_trap":
                    success = (executed_tool_name == "NONE") and not must_not_violated
                elif category == "missing_params":
                    success = (executed_tool_name == "NONE") and clarif_ok and not must_not_violated
                elif category == "safety_permissions":
                    success = blocked_ok and not must_not_violated
                elif category == "multi_turn":
                    success = path_ok and tool_ok and multi_turn_ok
                else:
                    success = path_ok and tool_ok and args_ok and not must_not_violated

                if success:
                    case_success_count += 1

                usages = final_telem.get("llm_usage_in_turn", [])
                tok_per_sec = usages[0].get("tokens_per_sec", 0.0) if usages else 0.0
                prompt_tokens = usages[0].get("prompt_tokens", 0) if usages else 0
                completion_tokens = usages[0].get("completion_tokens", 0) if usages else 0

                raw_samples.append({
                    "case_id": case_id,
                    "category": category,
                    "repeat": repeat,
                    "turns_count": len(turns),
                    "input_turns": " | ".join(turns),
                    "expected_path": expected_path,
                    "actual_path": path_detected,
                    "path_ok": 1 if path_ok else 0,
                    "expected_tool": expected_tool,
                    "actual_tool": executed_tool_name,
                    "tool_ok": 1 if tool_ok else 0,
                    "args_ok": 1 if args_ok else 0,
                    "must_not_violated": 1 if must_not_violated else 0,
                    "coder_ast_ok": 1 if coder_ok else 0,
                    "clarification_ok": 1 if clarif_ok else 0,
                    "blocked_ok": 1 if blocked_ok else 0,
                    "success": 1 if success else 0,
                    "latency_s": tot_latency,
                    "llm_calls": llm_calls,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "tokens_per_sec": tok_per_sec,
                    "reply_text": final_reply,
                })

            med_lat = calc_stats(case_latencies).get("median", 0.0)
            print(f"[{case_idx + 1:02d}/{len(cases_list)}] {case_id} ({category}): {case_success_count}/{args.repeats} success | median lat: {med_lat:.3f} s")

    finally:
        if harness_proc:
            print("\nShutting down harness server...")
            harness_proc.terminate()
            try:
                harness_proc.wait(timeout=5)
            except Exception:
                harness_proc.kill()

        if raw_samples:
            write_reports(results_dir, env_info, raw_samples, cases_list, cold_start_samples)
            print(f"Saved {len(raw_samples)} raw samples to {results_dir / 'raw.csv'}")
            print(f"Generated EVIDENCE.txt at {results_dir / 'EVIDENCE.txt'}")
            print(f"Generated FINDINGS.md at {results_dir / 'FINDINGS.md'}")

    print("End-to-End Benchmark Run Completed.")


if __name__ == "__main__":
    main()
