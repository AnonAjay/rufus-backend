# Rufus E2E Benchmark Label Disputes

**Suite Run ID**: `20261122_111352`  
**Reference Cases File**: `benchmarks/e2e/cases.yaml` (commit `00b98540ae7e3c320e9065ff520f010c2201c20a`)  
**Status**: Recorded without editing `cases.yaml`

---

## 1. Parameter Name & Type Mismatch: System Volume
- **Affected Cases**:
  - `B01_volume_exact_65`: `expected_args: {level: 65}`
  - `B02_volume_exact_40`: `expected_args: {level: 40}`
  - `B07_volume_exact_80`: `expected_args: {level: 80}`
  - `B08_volume_exact_20`: `expected_args: {level: 20}`
- **Dispute Description**:
  1. **Schema vs Graph Inconsistency**:
     - In `app/agent/tools.py` lines 615-635 (`TOOL_DEFINITIONS`):
       ```json
       "properties": {
           "action": {"type": "string", "enum": ["get", "set", "up", "down", "mute", "unmute"]},
           "level": {"type": "integer", "description": "Target volume percentage (0 to 100)"}
       }
       ```
     - In `app/agent/graph.py` line 427:
       ```python
       elif tool_name == "system_volume":
           val = tool_args.get("value")
       ```
       `graph.py` expects `value`, while `TOOL_DEFINITIONS` declares `level` to the model.
  2. **String vs Integer Coercion**:
     - `llama3.2` emits `{"action": "set", "level": "65"}` (string `"65"`).
     - `cases.yaml` requires strict integer `65`.
     - In `runner.py`, strict equality `exec_args.get("level") == expected_args["level"]` evaluates to `False` due to type mismatch (`"65" != 65`).

---

## 2. Unadvertised Application: Calculator
- **Affected Case**:
  - `B09_open_calculator`: `expected_tool: open_app`, `expected_args: {app_name: 'calculator'}`
- **Dispute Description**:
  - In `app/agent/tools.py` lines 504-518 (`open_app` tool definition):
    ```
    "description": "Opens an approved desktop application on Windows (WhatsApp, Antigravity, VS Code, Browser/Chrome, File Explorer)."
    "app_name": "Name of the application to open, e.g. 'whatsapp', 'vscode', 'browser', 'antigravity', 'explorer'"
    ```
  - In `app/agent/graph.py` lines 97-105 (`SHARED_TOOL_CAPABILITIES`):
    `"You have access to tools to open discovered desktop applications (WhatsApp, VS Code, Chrome, Brave, Discord, Spotify, Antigravity, Explorer)"`
  - Neither the tool description nor system prompt lists `calculator`.
  - When given `"Open calculator"`, the constrained local model selects `"explorer"` from the explicitly advertised allowlist. Labeling `calculator` as an expected argument without advertising it in the schema causes an unavoidable discrepancy.

---

## 3. Knowledge vs Observation Intent: Weather Forecast
- **Affected Case**:
  - `C01_web_search_weather`: `expected_path: 5`, `expected_tool: web_search`
  - **Query**: `"What is the latest weather forecast in Tokyo today?"`
- **Dispute Description**:
  - The production intent router contains an intent guard (`laya_intent_guard` in `app/agent/laya_router.py` lines 270-295) designed to prevent tool hallucination on knowledge questions.
  - The query is classified by `laya_intent_guard` as:
    `action_type: speech`, `persona: coder`, `confidence: 0.9200`, `reason: Pure knowledge inquiry routed to speech (coder mode)`.
  - Under the current production architecture, queries without explicit web-search action verbs ("search", "lookup", "google") are routed to Path 1 (Speech), not Path 5 (Observation Tool).
