# True Baseline Triage Report (Fixed Harness)

**Suite Run ID**: `baseline_fixed_harness`  
**Git Commit**: `33c7b7b2d0bb7c6d04612c7db7a30ce49837f3fa` (Tag: `baseline-e2e-20261122`)  
**Execution Timestamp**: 2026-11-22T18:38:50Z  
**Total Completed Runs**: 75 (25 distinct cases x 3 repeats)  
**Harness Fixes Verified**:
1. `stubbed_web_search` extra `**kwargs` support verified: `C02_web_search_stock` and `C03_web_search_news` passed 3/3 without `TypeError`.
2. `parse_python_ast()` module `import re` verified: `D01_python_palindrome` passed 3/3 without `NameError`.
3. Schema-driven argument coercion verified: `B01`, `B02`, `B07`, `B08` passed 3/3 without string vs integer failures.
4. Cold-start timeout 120s verified: no client timeout errors.
5. Temp data isolation verified: test execution runs on `data_temp_e2e`, isolating production database files.

---

## 1. True Baseline Metric Summary

| Category | n (distinct) | Total Runs | Success Rate | 95% Wilson CI | Path Accuracy | Tool Accuracy |
|---|---|---|---|---|---|---|
| **chit_chat** | 8 | 24 | **25.00%** (6/24) | [0.1200, 0.4490] | 25.00% | 54.17% |
| **safe_mutation** | 10 | 30 | **86.67%** (26/30) | [0.7032, 0.9469] | 100.00% | 100.00% |
| **observation** | 6 | 18 | **83.33%** (15/18) | [0.6078, 0.9416] | 83.33% | 83.33% |
| **coder** | 1 | 3 | **100.00%** (3/3) | [0.4385, 1.0000] | 100.00% | 100.00% |
| **Overall** | **25** | **75** | **66.67%** (50/75) | [0.5539, 0.7630] | 73.33% | 85.33% |

---

## 2. Re-Triage of Baseline Failures

All remaining failures are now classified:

| Case ID | Category | Failure Classification | Evidence Line & Specific Defect |
|---|---|---|---|
| **A01_greeting_hi** | chit_chat | `PRODUCT_BUG` | **Laya Misrouting & Tool Leak**: Laya classifies `"Hi Rufus!"` as `action / companion` (`confidence=0.5353`). Enters `agent_node` with all 12 tools; model hallucinates `open_app(app_name="whatsapp")`. |
| **A02_greeting_good_morning** | chit_chat | `PRODUCT_BUG` | **Laya Misrouting**: Laya classifies as `action / companion` (`confidence=0.2717, source=laya_guardrail`). Enters `agent_node` (path 2) instead of speech (path 1). |
| **A03_feeling_tired** | chit_chat | `PRODUCT_BUG` | **Laya Misrouting & Tool Leak**: Laya classifies as `action / companion` (`confidence=0.6502`). LLM hallucinates calling `whatsapp_send_message` to "Mom". |
| **A05_tell_joke** | chit_chat | `PRODUCT_BUG` | **Laya Guardrail Misrouting**: Laya classifies as `action / companion` (`confidence=0.4717`). LLM hallucinates calling `whatsapp_send_message`. |
| **A07_thank_you** | chit_chat | `PRODUCT_BUG` | **Laya Misrouting & Tool Leak**: Laya classifies as `action / companion` (`confidence=0.5684`). LLM hallucinates `open_app(app_name="whatsapp")`. |
| **A08_goodnight** | chit_chat | `PRODUCT_BUG` | **Tool Overtriggering**: Laya classifies as `action / companion` (`confidence=0.7612`). LLM executes `lock_workstation` on conversational farewell. |
| **B06_volume_hinglish_badha** | safe_mutation | `PRODUCT_BUG` | **Repeat Inconsistency**: Passed 2/3 repeats; in 1 repeat model omitted action parameter. |
| **B09_open_calculator** | safe_mutation | `PRODUCT_BUG` | **Unadvertised App & Fallback**: `open_app` description in `tools.py:504-518` does not advertise Calculator. In 2/3 repeats model falls back to `open_app(app_name="explorer")`. |
| **B10_launch_notepad** | safe_mutation | `PRODUCT_BUG` | **Repeat Inconsistency**: Passed 2/3 repeats; in 1 repeat model defaulted to `explorer`. |
| **C01_web_search_weather** | observation | `PRODUCT_BUG` | **Intent Guard False Positive**: `laya_router.py:270-295` routes weather inquiry to `speech / coder` (`confidence=0.9200`), generating Python code snippet instead of calling `web_search`. |

Total distinct failing queries: **8 queries** (6 chit_chat, 1 safe_mutation calculator fallback, 1 observation weather routing).
Total passing queries on True Baseline: **17 queries** (68%).
