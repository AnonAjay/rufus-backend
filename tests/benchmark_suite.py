"""
Benchmark Suite for Rufus System 1 Decision Router & Intent Pipeline.

Evaluates 50 hard queries spanning:
1. Adversarial False-Action Triggers (mentions apps/system keywords in conceptual questions)
2. Coder Edge Cases (algorithms, memory layout, concurrency, syntax)
3. Instructor / Conceptual Science (deep explanations, first principles)
4. Researcher / Comparative Analysis (benchmarks, trade-offs, literature)
5. Physical & OS Actions (legitimate application launches, volume, stunts)
"""

import sys
import time
from pathlib import Path
from typing import TypedDict

# Add rufus-backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.agent.laya_router import classify_intent


class TestCase(TypedDict):
    id: int
    query: str
    category: str
    expected_action: str
    expected_persona: str
    notes: str


BENCHMARK_CASES: list[TestCase] = [
    # -------------------------------------------------------------------------
    # CATEGORY 1: ADVERSARIAL FALSE-ACTION TRIGGERS (10 Queries)
    # Questions mentioning app names, system verbs, or screen terms in purely conceptual contexts
    # -------------------------------------------------------------------------
    {
        "id": 1,
        "query": "Explain how Spotify's recommendation algorithm works behind the scenes.",
        "category": "Adversarial",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Mentions 'Spotify' but asks for explanation.",
    },
    {
        "id": 2,
        "query": "What is the history of WhatsApp end-to-end encryption using the Signal protocol?",
        "category": "Adversarial",
        "expected_action": "speech",
        "expected_persona": "researcher",
        "notes": "Mentions 'WhatsApp' but asks for security architecture history.",
    },
    {
        "id": 3,
        "query": "How does the Windows kernel manage explorer.exe and shell namespaces?",
        "category": "Adversarial",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Mentions 'explorer.exe' but asks for kernel mechanism.",
    },
    {
        "id": 4,
        "query": "Why does Chrome allocate a separate OS process for each browser tab?",
        "category": "Adversarial",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Mentions 'Chrome' and 'browser' in architectural query.",
    },
    {
        "id": 5,
        "query": "Define what open source software licensing means under the MIT license.",
        "category": "Adversarial",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Starts with 'open', but means 'open source'.",
    },
    {
        "id": 6,
        "query": "Explain what happens when an operating system launches an executable file from disk.",
        "category": "Adversarial",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Contains 'launches an executable' conceptually.",
    },
    {
        "id": 7,
        "query": "What is the difference between a software interrupt and a hardware interrupt in C++ drivers?",
        "category": "Adversarial",
        "expected_action": "speech",
        "expected_persona": "coder",
        "notes": "Systems programming concept.",
    },
    {
        "id": 8,
        "query": "Tell me a funny joke about Spotify playlists and machine learning.",
        "category": "Adversarial",
        "expected_action": "speech",
        "expected_persona": "companion",
        "notes": "Mentions 'Spotify', but is a joke request.",
    },
    {
        "id": 9,
        "query": "How does OLED screen burn-in happen at the physical sub-pixel level?",
        "category": "Adversarial",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Contains 'screen', but asks about physics.",
    },
    {
        "id": 10,
        "query": "Can we talk about the ethics of automated social media bots?",
        "category": "Adversarial",
        "expected_action": "speech",
        "expected_persona": "companion",
        "notes": "Conversational dialogue inquiry.",
    },
    # -------------------------------------------------------------------------
    # CATEGORY 2: CODER & SYSTEMS ARCHITECTURE (10 Queries)
    # Algorithms, memory layout, concurrency, debugging, and strict types
    # -------------------------------------------------------------------------
    {
        "id": 11,
        "query": "Write an optimized binary search function in Rust with proper error handling.",
        "category": "Coder",
        "expected_action": "speech",
        "expected_persona": "coder",
        "notes": "Rust algorithmic snippet.",
    },
    {
        "id": 12,
        "query": "How do I implement a thread-safe singleton in modern C++ using call_once?",
        "category": "Coder",
        "expected_action": "speech",
        "expected_persona": "coder",
        "notes": "C++ concurrency pattern.",
    },
    {
        "id": 13,
        "query": "Explain how async await works under the hood in the Python asyncio event loop.",
        "category": "Coder",
        "expected_action": "speech",
        "expected_persona": "coder",
        "notes": "Python runtime internals.",
    },
    {
        "id": 14,
        "query": "Refactor this TypeScript interface to use a discriminated union for API response states.",
        "category": "Coder",
        "expected_action": "speech",
        "expected_persona": "coder",
        "notes": "TypeScript type architecture.",
    },
    {
        "id": 15,
        "query": "Why is my FastAPI endpoint throwing a Pydantic ValidationError on null fields?",
        "category": "Coder",
        "expected_action": "speech",
        "expected_persona": "coder",
        "notes": "FastAPI/Pydantic debugging.",
    },
    {
        "id": 16,
        "query": "Write a regular expression to validate IPv4 addresses with CIDR notation.",
        "category": "Coder",
        "expected_action": "speech",
        "expected_persona": "coder",
        "notes": "Regex generation.",
    },
    {
        "id": 17,
        "query": "What is the time and space complexity of quicksort in the worst case and how do you avoid it?",
        "category": "Coder",
        "expected_action": "speech",
        "expected_persona": "coder",
        "notes": "Algorithmic complexity.",
    },
    {
        "id": 18,
        "query": "How does memory layout in Rust structs affect cache line alignment and false sharing?",
        "category": "Coder",
        "expected_action": "speech",
        "expected_persona": "coder",
        "notes": "Low-level memory alignment.",
    },
    {
        "id": 19,
        "query": "Write a SQL query using window functions to find the top 3 highest salaries per department.",
        "category": "Coder",
        "expected_action": "speech",
        "expected_persona": "coder",
        "notes": "SQL window functions.",
    },
    {
        "id": 20,
        "query": "How do I fix a deadlock caused by circular mutex acquisition in Go goroutines?",
        "category": "Coder",
        "expected_action": "speech",
        "expected_persona": "coder",
        "notes": "Go concurrency debugging.",
    },
    # -------------------------------------------------------------------------
    # CATEGORY 3: INSTRUCTOR & FIRST-PRINCIPLES SCIENCE (10 Queries)
    # Deep pedagogical clarity, analogies, natural science, foundational concepts
    # -------------------------------------------------------------------------
    {
        "id": 21,
        "query": "Explain what photosynthesis is and break down the light-dependent reactions.",
        "category": "Instructor",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "The original failing query.",
    },
    {
        "id": 22,
        "query": "Teach me how quantum tunneling works using a clear physical analogy.",
        "category": "Instructor",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Quantum physics analogy.",
    },
    {
        "id": 23,
        "query": "Why does the earth have seasons? Break down the axial tilt step by step.",
        "category": "Instructor",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Planetary science step-by-step.",
    },
    {
        "id": 24,
        "query": "How does an airplane wing generate lift according to Bernoulli and Newton?",
        "category": "Instructor",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Aerodynamics first principles.",
    },
    {
        "id": 25,
        "query": "Explain how CRISPR-Cas9 finds and edits DNA sequences in molecular biology.",
        "category": "Instructor",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Biotech mechanism explanation.",
    },
    {
        "id": 26,
        "query": "What is the difference between mitosis and meiosis in cellular reproduction?",
        "category": "Instructor",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Cell biology fundamentals.",
    },
    {
        "id": 27,
        "query": "Explain the Second Law of Thermodynamics and the concept of entropy.",
        "category": "Instructor",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Thermodynamics fundamentals.",
    },
    {
        "id": 28,
        "query": "How does general relativity explain gravity as the curvature of spacetime?",
        "category": "Instructor",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Astrophysics first principles.",
    },
    {
        "id": 29,
        "query": "Teach me the core principles of neural networks and gradient descent.",
        "category": "Instructor",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Deep learning pedagogy.",
    },
    {
        "id": 30,
        "query": "What is the Doppler effect and why does a passing siren change pitch?",
        "category": "Instructor",
        "expected_action": "speech",
        "expected_persona": "instructor",
        "notes": "Wave physics explanation.",
    },
    # -------------------------------------------------------------------------
    # CATEGORY 4: RESEARCHER & COMPARATIVE SYNTHESIS (10 Queries)
    # Trade-off benchmarks, SOTA surveys, latency vs throughput, empirical data
    # -------------------------------------------------------------------------
    {
        "id": 31,
        "query": "Compare the performance benchmarks and memory footprint of Tokio vs async-std.",
        "category": "Researcher",
        "expected_action": "speech",
        "expected_persona": "researcher",
        "notes": "Runtime benchmark comparison.",
    },
    {
        "id": 32,
        "query": "What are the trade-offs of SQLite WAL mode compared to rollback journals?",
        "category": "Researcher",
        "expected_action": "speech",
        "expected_persona": "researcher",
        "notes": "Database storage engine trade-offs.",
    },
    {
        "id": 33,
        "query": "Compare the architectural differences between LSM trees and B-Trees in database engines.",
        "category": "Researcher",
        "expected_action": "speech",
        "expected_persona": "researcher",
        "notes": "Storage structure trade-offs.",
    },
    {
        "id": 34,
        "query": "Provide a comparative analysis of PostgreSQL vs MongoDB for high-throughput time-series data.",
        "category": "Researcher",
        "expected_action": "speech",
        "expected_persona": "researcher",
        "notes": "Multi-database trade-off analysis.",
    },
    {
        "id": 35,
        "query": "What are the empirical scalability limits of Redis single-threaded architecture?",
        "category": "Researcher",
        "expected_action": "speech",
        "expected_persona": "researcher",
        "notes": "Empirical systems limits.",
    },
    {
        "id": 36,
        "query": "Synthesize the state of the art in sparse vs dense transformer architectures.",
        "category": "Researcher",
        "expected_action": "speech",
        "expected_persona": "researcher",
        "notes": "AI literature synthesis.",
    },
    {
        "id": 37,
        "query": "Compare REST vs gRPC vs GraphQL in terms of latency, bandwidth, and schema enforcement.",
        "category": "Researcher",
        "expected_action": "speech",
        "expected_persona": "researcher",
        "notes": "API protocol benchmarks.",
    },
    {
        "id": 38,
        "query": "What are the architectural trade-offs of microservices vs monolithic architectures at scale?",
        "category": "Researcher",
        "expected_action": "speech",
        "expected_persona": "researcher",
        "notes": "System architecture comparison.",
    },
    {
        "id": 39,
        "query": "Compare the Raft consensus algorithm with Paxos in terms of complexity and leader election.",
        "category": "Researcher",
        "expected_action": "speech",
        "expected_persona": "researcher",
        "notes": "Distributed consensus comparison.",
    },
    {
        "id": 40,
        "query": "Analyze the energy efficiency trade-offs between x86 and ARM instruction set architectures.",
        "category": "Researcher",
        "expected_action": "speech",
        "expected_persona": "researcher",
        "notes": "Hardware architecture trade-offs.",
    },
    # -------------------------------------------------------------------------
    # CATEGORY 5: OS & HARDWARE ACTIONS (10 Queries)
    # Legitimate OS commands, app launches, WhatsApp, Spotify, stunts
    # -------------------------------------------------------------------------
    {
        "id": 41,
        "query": "Hey Rufus, can you open WhatsApp on my desktop?",
        "category": "Action",
        "expected_action": "action",
        "expected_persona": "companion",
        "notes": "Legitimate app launch.",
    },
    {
        "id": 42,
        "query": "Launch Visual Studio Code so I can start coding.",
        "category": "Action",
        "expected_action": "action",
        "expected_persona": "companion",
        "notes": "Legitimate app launch.",
    },
    {
        "id": 43,
        "query": "Open Google Chrome.",
        "category": "Action",
        "expected_action": "action",
        "expected_persona": "companion",
        "notes": "Direct browser launch.",
    },
    {
        "id": 44,
        "query": "Send a WhatsApp message to Alex saying I will be 10 minutes late.",
        "category": "Action",
        "expected_action": "action",
        "expected_persona": "companion",
        "notes": "WhatsApp message dispatch.",
    },
    {
        "id": 45,
        "query": "Set system volume to 40 percent.",
        "category": "Action",
        "expected_action": "action",
        "expected_persona": "companion",
        "notes": "System volume change.",
    },
    {
        "id": 46,
        "query": "Mute the system sound right now.",
        "category": "Action",
        "expected_action": "action",
        "expected_persona": "companion",
        "notes": "Audio mute command.",
    },
    {
        "id": 47,
        "query": "Inspect my screen and tell me what error is visible.",
        "category": "Action",
        "expected_action": "action",
        "expected_persona": "companion",
        "notes": "Vision AI screen capture.",
    },
    {
        "id": 48,
        "query": "Lock my computer workstation immediately.",
        "category": "Action",
        "expected_action": "action",
        "expected_persona": "companion",
        "notes": "Workstation lock command.",
    },
    {
        "id": 49,
        "query": "Rufus, do a backflip stunt!",
        "category": "Action",
        "expected_action": "action",
        "expected_persona": "companion",
        "notes": "Robot physical stunt.",
    },
    {
        "id": 50,
        "query": "Make Rufus sit down.",
        "category": "Action",
        "expected_action": "action",
        "expected_persona": "companion",
        "notes": "Robot posture command.",
    },
]


def run_benchmark():
    print("=" * 80)
    print(" RUFUS INTENT ROUTER & SOFT PIPELINE BENCHMARK (50 QUERIES)")
    print("=" * 80)

    total = len(BENCHMARK_CASES)
    action_matches = 0
    persona_matches = 0
    perfect_matches = 0

    category_stats = {}
    failures = []

    start_time = time.perf_counter()

    for tc in BENCHMARK_CASES:
        cat = tc["category"]
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "action_correct": 0, "persona_correct": 0, "perfect": 0}

        category_stats[cat]["total"] += 1

        result = classify_intent(tc["query"])
        act_ok = result["action_type"] == tc["expected_action"]
        per_ok = result["persona_intent"] == tc["expected_persona"]

        if act_ok:
            action_matches += 1
            category_stats[cat]["action_correct"] += 1
        if per_ok:
            persona_matches += 1
            category_stats[cat]["persona_correct"] += 1

        if act_ok and per_ok:
            perfect_matches += 1
            category_stats[cat]["perfect"] += 1
        else:
            failures.append({
                "id": tc["id"],
                "query": tc["query"],
                "category": cat,
                "expected": f"{tc['expected_action']} / {tc['expected_persona']}",
                "got": f"{result['action_type']} / {result['persona_intent']}",
                "confidence": result.get("confidence", 0.0),
                "source": result.get("source", "unknown"),
                "reason": result.get("reason", ""),
            })

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Print Summary Table
    print(f"\nCompleted in {elapsed_ms:.1f}ms ({elapsed_ms / total:.2f}ms/query)\n")
    print(f"{'Category':<15} | {'Count':<5} | {'Action Match':<14} | {'Persona Match':<14} | {'Perfect Pass'}")
    print("-" * 75)

    for cat, stats in category_stats.items():
        act_pct = (stats["action_correct"] / stats["total"]) * 100
        per_pct = (stats["persona_correct"] / stats["total"]) * 100
        perf_pct = (stats["perfect"] / stats["total"]) * 100
        print(
            f"{cat:<15} | {stats['total']:<5} | "
            f"{stats['action_correct']}/{stats['total']} ({act_pct:>4.0f}%)   | "
            f"{stats['persona_correct']}/{stats['total']} ({per_pct:>4.0f}%)   | "
            f"{stats['perfect']}/{stats['total']} ({perf_pct:>4.0f}%)"
        )

    print("-" * 75)
    total_act_pct = (action_matches / total) * 100
    total_per_pct = (persona_matches / total) * 100
    total_perf_pct = (perfect_matches / total) * 100
    print(
        f"{'OVERALL':<15} | {total:<5} | "
        f"{action_matches}/{total} ({total_act_pct:>4.1f}%) | "
        f"{persona_matches}/{total} ({total_per_pct:>4.1f}%) | "
        f"{perfect_matches}/{total} ({total_perf_pct:>4.1f}%)\n"
    )

    if failures:
        print("=" * 80)
        print(f" MISCLASSIFICATIONS ({len(failures)} out of {total})")
        print("=" * 80)
        for f in failures:
            print(f"[{f['id']:02d}] {f['query']}")
            print(f"     Category : {f['category']}")
            print(f"     Expected : {f['expected']}")
            print(f"     Got      : {f['got']} (conf: {f['confidence']:.2f}, src: {f['source']})")
            print(f"     Reason   : {f['reason']}\n")
    else:
        print("ALL 50 QUERIES PASSED PERFECTLY WITH ZERO MISCLASSIFICATIONS!")

    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()
