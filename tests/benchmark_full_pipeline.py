"""
End-to-End LangGraph Pipeline Stopwatch Benchmark.
Measures wall-clock latency (seconds) across all 5 distinct execution paths:
1. Pure Chit-Chat (router -> chat_node -> END)
2. Safe Mutation Action (router -> agent_node -> tools_node -> END [Short-Circuit])
3. Action Route / No-Tool Fallback (router -> agent_node -> END)
4. Coder Generation (router -> chat_node [Coder] -> END)
5. Observation Action (router -> agent_node -> tools_node -> respond_node -> END)
"""

import json
import sys
import time
import urllib.request
from typing import Any


BENCHMARK_CASES = [
    {
        "id": 1,
        "name": "Pure Chit-Chat",
        "query": "Hey Rufus, how's your day going so far?",
        "expected_path": "chat_node (Speech)",
        "notes": "Short conversational turn, no tool schemas in prompt.",
    },
    {
        "id": 2,
        "name": "Safe Mutation Action",
        "query": "Set system volume to 65",
        "expected_path": "tools_node -> END (Short-Circuit)",
        "notes": "Fast OS mutation; Call 2 eliminated via skip_respond.",
    },
    {
        "id": 3,
        "name": "Action Route (No Tool)",
        "query": "I might want to listen to some music or maybe not, what do you think?",
        "expected_path": "agent_node -> END",
        "notes": "Action keywords present but no concrete command emitted.",
    },
    {
        "id": 4,
        "name": "Coder Generation",
        "query": "Write a Python function to check if a string is a palindrome with docstring and type hints.",
        "expected_path": "chat_node (Coder)",
        "notes": "High output token count, AST markdown code fences.",
    },
    {
        "id": 5,
        "name": "Observation Action",
        "query": "Search the web for the release date of Python 3.14",
        "expected_path": "tools_node -> respond_node -> END",
        "notes": "Full ReAct loop: Call 1 + DuckDuckGo I/O + Call 2 synthesis.",
    },
]


def run_benchmark():
    print("=" * 80)
    print("      RUFUS LANGGRAPH END-TO-END STOPWATCH BENCHMARK")
    print("=" * 80)
    print(f"Target Endpoint: http://127.0.0.1:8000/agent/chat")
    print(f"Total Benchmark Cases: {len(BENCHMARK_CASES)}\n")

    results = []

    for case in BENCHMARK_CASES:
        session_id = f"benchmark-session-{case['id']}-{int(time.time())}"
        payload = {
            "session_id": session_id,
            "message": case["query"],
        }
        req = urllib.request.Request(
            "http://127.0.0.1:8000/agent/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        print(f"[{case['id']}/{len(BENCHMARK_CASES)}] Testing: '{case['name']}'...")
        print(f"     Query: \"{case['query']}\"")
        print(f"     Expected Path: {case['expected_path']}")

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                elapsed = time.perf_counter() - t0
                status_code = resp.status
                body = json.loads(resp.read().decode("utf-8"))

                reply = body.get("reply", "")
                actions = body.get("actions", [])
                action_type = body.get("action_type", "")
                model = body.get("model_used", "")
                confidence = body.get("confidence", 0.0)

                # Approximate tokens (words * 1.33)
                words = len(reply.split())
                approx_tokens = int(words * 1.33)
                tok_per_sec = approx_tokens / elapsed if elapsed > 0 else 0.0

                print(f"     Status: {status_code} | Wall-Clock Latency: {elapsed:.3f}s")
                print(f"     Action Type: {action_type} | Actions: {actions}")
                print(f"     Tokens Out: ~{approx_tokens} ({tok_per_sec:.1f} tok/s)")
                snippet = reply[:120].replace('\n', ' ')
                print(f"     Reply Snippet: \"{snippet}...\"\n")

                results.append({
                    "id": case["id"],
                    "name": case["name"],
                    "query": case["query"],
                    "expected_path": case["expected_path"],
                    "latency_sec": round(elapsed, 3),
                    "action_type": action_type,
                    "actions": actions,
                    "approx_tokens": approx_tokens,
                    "tok_per_sec": round(tok_per_sec, 1),
                    "model": model,
                    "confidence": confidence,
                    "success": True,
                })
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"     FAILED after {elapsed:.3f}s: {exc}\n")
            results.append({
                "id": case["id"],
                "name": case["name"],
                "query": case["query"],
                "expected_path": case["expected_path"],
                "latency_sec": round(elapsed, 3),
                "error": str(exc),
                "success": False,
            })

    print("=" * 80)
    print("                     BENCHMARK SUMMARY MATRIX")
    print("=" * 80)
    print(f"{'#':<3} | {'Path / Test Case':<24} | {'Latency':<10} | {'Tokens':<8} | {'Actions Executed':<22}")
    print("-" * 80)
    for r in results:
        if r["success"]:
            acts = ", ".join(r["actions"]) if r["actions"] else "None (Speech)"
            print(f"{r['id']:<3} | {r['name']:<24} | {r['latency_sec']:>6.3f}s   | {r['approx_tokens']:>5} tok | {acts[:22]:<22}")
        else:
            print(f"{r['id']:<3} | {r['name']:<24} | FAILED ({r.get('error', '')[:20]})")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()
