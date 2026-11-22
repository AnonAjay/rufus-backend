# Rufus Benchmark & Evidence Audit Suite

This directory contains measured, reproducible, interview-defensible benchmarks and evidence auditing scripts for the Rufus AI companion robot dog and desktop assistant repository.

All numbers in `benchmarks/results/EVIDENCE.txt` and raw CSV logs are produced directly on the host machine in strict accordance with empirical benchmarking principles:
- No invented or recalled metrics.
- Every comparison uses an interleaved named baseline executed in the same session (`A, B, A, B...`).
- Discarded warm-up runs (min 3) reported separately as cold-start.
- Wilson 95% confidence intervals for proportions.
- Bootstrap 95% confidence intervals (10,000 resamples) for differences.
- Raw per-trial samples recorded to CSV under `benchmarks/results/`.
- Unreviewed evaluation datasets explicitly marked `reviewed = False` and reported as `PROVISIONAL`.

---

## Directory Structure

```
benchmarks/
├── README.md                      # Replication guide and audit protocol
├── stats_utils.py                 # Statistical utilities (Wilson CI, Bootstrap CI, IQR, percentiles)
├── dataset.py                     # 23-query test dataset with clear and borderline test cases
├── benchmark_whatsapp.py          # WhatsApp open_app & whatsapp_send_message A/B tests
├── benchmark_agent_routing.py     # Laya Intent Router vs Naive Keyword baseline & function call trace
├── benchmark_permissions.py       # Pre-generation schema pruning & post-generation gatekeeper
├── benchmark_cold_start.py        # Backend process cold-start import latency
├── run_all.py                     # Master test runner
└── results/
    ├── EVIDENCE.txt               # Complete audit report formatted to exact schema
    ├── open_app_samples.csv       # Raw trial data for open_app
    ├── whatsapp_send_samples.csv  # Raw trial data for whatsapp_send_message
    ├── routing_samples.csv        # Raw trial data for intent routing
    ├── permissions_samples.csv    # Raw trial data for permissions filtering
    └── cold_start_samples.csv     # Raw trial data for process import
```

---

## How to Reproduce

### 1. Requirements
- Python 3.11+ (tested on Python 3.14.2)
- Dependencies installed from root `requirements.txt`:
  ```bash
  pip install -r requirements.txt
  ```

### 2. Run the Full Suite
Execute the master runner from the repository root:
```bash
python benchmarks/run_all.py
```
This will run all benchmarks sequentially, output progress and timing, log raw CSV data into `benchmarks/results/`, and overwrite `benchmarks/results/EVIDENCE.txt`.

### 3. Run Individual Benchmarks
You can also run any specific benchmark module independently:
- **WhatsApp Subsystem**:
  ```bash
  python benchmarks/benchmark_whatsapp.py
  ```
- **Agent Intent Routing & Function Calls**:
  ```bash
  python benchmarks/benchmark_agent_routing.py
  ```
- **App & Skill Permissions Engine**:
  ```bash
  python benchmarks/benchmark_permissions.py
  ```
- **Backend Cold Start**:
  ```bash
  python benchmarks/benchmark_cold_start.py
  ```
