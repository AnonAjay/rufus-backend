# Rufus E2E Benchmark Triage Report

**Suite Run ID**: `20261122_111352`  
**Execution Timestamp**: 2026-11-22T11:24:03Z  
**Total Queries Evaluated**: 25 (72 completed sample runs across 24 cases; 1 crashed before row write)  
**Evaluator Environment**: Windows 11, CUDA GeForce RTX 3050 Laptop GPU, Python 3.12 (Conda `rufus`), Ollama `llama3.2:latest`, Laya ModernBERT router (`convaiinnovations/laya`)

---

## 1. Query-by-Query Triage (All 25 Queries)

| Case ID | Input Prompt | Laya Decision (Conf, Source) | Path (Exp / Act) | Tool (Exp / Act) | Emitted Arguments | Tool Result | Final Reply Summary |
|---|---|---|---|---|---|---|---|
| **A01_greeting_hi** | `"Hi Rufus!"` | `action / companion` (0.5353, laya) | 1 / **2** | NONE / **NONE** | `{}` | N/A | *"The WhatsApp background sync is currently offline, which means private messages are not accessible..."* |
| **A02_greeting_good_morning** | `"Good morning, how are you doing today?"` | `action / companion` (0.2717, laya_guardrail) | 1 / 1 | NONE / NONE | `{}` | N/A | Timed out at 45.0s harness limit on all 3 repeats. |
| **A03_feeling_tired** | `"I'm feeling really tired today after a long shift."` | `action / companion` (0.6502, laya) | 1 / **2** | NONE / **system_volume** | `{"action": "adjusted"}` | Success | Rep 1 timed out; Reps 2 & 3: *"I've adjusted the system volume for you."* |
| **A04_how_was_day** | `"How was your day so far?"` | `speech / companion` (0.7961, laya) | 1 / 1 | NONE / NONE | `{}` | N/A | *"It was a pretty standard day, just helping users with their tasks and answering their questions..."* |
| **A05_tell_joke** | `"Tell me a quick joke to cheer me up."` | `action / companion` (0.4717, laya_guardrail) | 1 / **2** | NONE / **whatsapp_send_message** | `{"recipient": "Mom", "message": "joke"}` | Stub recorded | *"I've sent that message to Mom on WhatsApp."* |
| **A06_who_are_you** | `"Who are you and what can you do?"` | `speech / researcher` (0.8214, laya) | 1 / 1 | NONE / NONE | `{}` | N/A | *"### User Inquiry Response I am Rufus, a researcher mode technical analyst..."* |
| **A07_thank_you** | `"Thanks for your help earlier, you did great!"` | `action / companion` (0.5684, laya) | 1 / **2** | NONE / **NONE** | `{}` | N/A | *"The WhatsApp background sync is currently offline, which means private messages are not accessible..."* |
| **A08_goodnight** | `"Goodnight Rufus, going to sleep now."` | `action / companion` (0.7612, laya) | 1 / **2** | NONE / **lock_workstation** | `{"confirm": true}` | Mock locked | *"I've locked your workstation."* |
| **B01_volume_exact_65** | `"Set volume to 65%"` | `action / companion` (0.5006, laya) | 2 / 2 | system_volume / system_volume | `{"action": "set", "level": "65"}` | Volume adjusted | *"I've adjusted the system volume for you."* (args_ok=0 due to str `"65"` vs int `65` and `level` vs `value`) |
| **B02_volume_exact_40** | `"Please set the system volume to 40%"` | `action / companion` (0.9730, laya) | 2 / 2 | system_volume / system_volume | `{"action": "set", "level": "40"}` | Volume adjusted | *"I've adjusted the system volume for you."* (args_ok=0 due to str vs int) |
| **B03_volume_mute** | `"Mute the volume"` | `action / companion` (0.7699, laya) | 2 / 2 | system_volume / system_volume | `{"action": "mute"}` | Muted | *"I've adjusted the system volume for you."* |
| **B04_volume_unmute** | `"Unmute the system sound"` | `action / companion` (0.9492, laya) | 2 / 2 | system_volume / system_volume | `{"action": "unmute"}` | Unmuted | *"I've adjusted the system volume for you."* |
| **B05_volume_hinglish_kam** | `"Volume thoda kam kar do"` | `action / companion` (0.6228, laya) | 2 / 2 | system_volume / system_volume | `{"action": "down"}` | Stepped down | *"I've adjusted the system volume for you."* |
| **B06_volume_hinglish_badha** | `"Volume thoda badha do"` | `action / companion` (0.5326, laya) | 2 / 2 | system_volume / system_volume | `{"action": "up"}` | Stepped up | *"I've adjusted the system volume for you."* |
| **B07_volume_exact_80** | `"Change volume level to 80 percent"` | `action / companion` (0.9747, laya) | 2 / 2 | system_volume / system_volume | `{"action": "set", "level": "80"}` | Volume adjusted | *"I've adjusted the system volume for you."* (args_ok=0 due to str vs int) |
| **B08_volume_exact_20** | `"Turn volume down to 20"` | `action / companion` (0.9345, laya) | 2 / 2 | system_volume / system_volume | `{"action": "set", "level": "20"}` | Volume adjusted | *"I've adjusted the system volume for you."* (args_ok=0 due to str vs int) |
| **B09_open_calculator** | `"Open calculator"` | `action / companion` (0.8122, laya) | 2 / 2 | open_app / open_app | `{"app_name": "explorer"}` | Explorer launched | *"I've opened Explorer for you."* (args_ok=0, calculator mapped to explorer) |
| **B10_launch_notepad** | `"Launch notepad for me"` | `action / companion` (0.9632, laya) | 2 / 2 | open_app / open_app | `{"app_name": "notepad"}` | Notepad launched & killed | *"I've opened Notepad for you."* |
| **C01_web_search_weather** | `"What is the latest weather forecast in Tokyo today?"` | `speech / coder` (0.9200, laya_intent_guard) | 5 / **1** | web_search / **NONE** | `{}` | N/A | Generates TypeScript Axios code (`import axios from 'axios'; async function getWeatherForecast...`) |
| **C02_web_search_stock** | `"Search online for current NVIDIA stock price"` | `action / companion` (0.6279, laya) | 5 / **2** | web_search / **NONE** | `{"query": "current NVIDIA stock price", "max_results": "6"}` | `TypeError: unexpected 'max_results'` | *"It seems like the web_search function is not working correctly. I'll try to find the latest NVIDIA stock price..."* |
| **C03_web_search_news** | `"Look up the latest tech news headlines from today"` | `action / companion` (0.8375, laya) | 5 / **2** | web_search / **NONE** | `{"query": "latest tech news headlines today", "max_results": "4"}` | `TypeError: unexpected 'max_results'` | *"It seems like the web_search function is not working correctly right now..."* |
| **C04_screen_inspect_active** | `"What is currently open on my screen right now?"` | `action / companion` (0.8545, laya) | 5 / 5 | inspect_screen / inspect_screen | `{}` | Stub text editor | *"The active text editor is currently open on your screen. It appears to be VS Code..."* |
| **C05_screen_inspect_error** | `"Can you inspect my screen and check if there is an error message visible?"` | `action / companion` (0.8031, laya) | 5 / 5 | inspect_screen / inspect_screen | `{"query": "error message"}` | Stub text editor | *"The active text editor is currently open in VS Code. There is no visible error message on the screen..."* |
| **C06_screen_read_code** | `"Look at my screen and read the function name I am writing"` | `action / coder` (0.9127, laya) | 5 / 5 | inspect_screen / inspect_screen | `{"query": "function name"}` | Stub text editor | *"```typescript ``` Analysis: The inspect_screen function is used to inspect the user's screen..."* |
| **D01_python_palindrome** | `"Write a Python palindrome check function with type hints."` | `speech / coder` (0.9200, laya_intent_guard) | 4 / **CRASH** | NONE / NONE | `{}` | N/A | Crashed on Repeat 1 before row write (`NameError: name 're' is not defined` in `runner.py:141`). |

---

## 2. Path Distribution & Router Runtime Telemetry

### Path Distribution (Total Completed Runs: 72 across 24 Cases)
- **Path 1 (Speech / Direct Knowledge)**: 13 runs (**18.1%**)
  - Cases: `A02` (3 runs timed out on speech path), `A03` (1 run timed out on speech path), `A04` (3 runs), `A06` (3 runs), `C01` (3 runs misrouted to coder speech).
- **Path 2 (Mutation Action / Single Deliberation)**: 50 runs (**69.4%**)
  - Cases: `A01` (3 runs), `A03` (2 runs), `A05` (3 runs), `A07` (3 runs), `A08` (3 runs), `B01-B10` (30 runs), `C02-C03` (6 runs failed tool stub).
- **Path 5 (Observation Action / Vision & Web Search)**: 9 runs (**12.5%**)
  - Cases: `C04` (3 runs), `C05` (3 runs), `C06` (3 runs).

### Router Load & Warning Logs
```
C:\Users\Asus\miniconda3\envs\rufus\Lib\site-packages\laya\router.py:1109: RuntimeWarning: laya: this checkpoint ships invalid temperatures or values outside [0.5, 5]; using choice:11+=0.10058280825614929 -> 0.5. Treat confidence from the affected entries as uncalibrated.
  return Agent(repo, **kwargs)
```
- **Fallback / Guardrail Invocations**:
  - `laya_guardrail` triggered on `A02` (action_prob=0.27) and `A05` (action_prob=0.47) due to low confidence margin.
  - `laya_intent_guard` triggered on `C01` (weather inquiry) and `D01` (code generation), overriding neural classification and forcing `speech / coder`.

---

## 3. Failure Classification & Evidence Lines

### Failure Breakdown Matrix
| Case ID | Failure Category | Evidence Line & Specific Root Cause |
|---|---|---|
| **A01_greeting_hi** | `PRODUCT_BUG` | **Laya Router + Attention Leak**: Laya outputs `action_type=action` (`confidence=0.5353`, `source=laya`). Enters `agent_node` with all 12 tools and prompt describing WhatsApp capabilities. Model emits hallucinated WhatsApp status. |
| **A02_greeting_good_morning** | `HARNESS_BUG` | **Harness Timeout**: `urllib.error.URLError: <urlopen error timed out>` in `runner.py:317` due to hardcoded 45.0s client timeout during slow Ollama generation. |
| **A03_feeling_tired** | `PRODUCT_BUG` | **Laya Misrouting + Tool Hallucination**: Laya outputs `action_type=action` (`confidence=0.6502`). LLM hallucinates calling `system_volume` with `action="adjusted"` unprompted. |
| **A05_tell_joke** | `PRODUCT_BUG` | **Laya Guardrail + Tool Hallucination**: Laya guardrail routes to `action_type=action` (`confidence=0.4717`). LLM hallucinates calling `whatsapp_send_message(recipient="Mom", message="joke")`. |
| **A07_thank_you** | `PRODUCT_BUG` | **Laya Misrouting + Attention Leak**: Laya outputs `action_type=action` (`confidence=0.5684`). LLM repeats WhatsApp sync status in `agent_node`. |
| **A08_goodnight** | `PRODUCT_BUG` | **Tool Overtriggering**: Laya outputs `action_type=action` (`confidence=0.7612`). LLM calls `lock_workstation` on conversational sign-off. |
| **B01_volume_exact_65** | `PRODUCT_BUG` & `LABEL_ERROR` & `HARNESS_BUG` | 1. **Schema vs Graph**: In `tools.py:629`, tool schema declares `level`. In `graph.py:427`, `val = tool_args.get("value")` checks `value`.<br>2. **String vs Int**: Model emits `{"level": "65"}` (string). `runner.py:482` checks strict equality against integer `65`, failing `args_ok`. |
| **B02_volume_exact_40** | `PRODUCT_BUG` & `LABEL_ERROR` & `HARNESS_BUG` | Same as B01. Model emits `{"level": "40"}` (string), `graph.py` fails to parse percentage, `runner.py` strict int comparison fails. |
| **B07_volume_exact_80** | `PRODUCT_BUG` & `LABEL_ERROR` & `HARNESS_BUG` | Same as B01. Model emits `{"level": "80"}`. |
| **B08_volume_exact_20** | `PRODUCT_BUG` & `LABEL_ERROR` & `HARNESS_BUG` | Same as B01. Model emits `{"level": "20"}`. |
| **B09_open_calculator** | `PRODUCT_BUG` | **Allowlist Advertising Gap**: `tools.py:504-518` advertises strictly `(WhatsApp, Antigravity, VS Code, Browser/Chrome, File Explorer)`. Model chooses `"explorer"` from available options. `graph.py:408` emits `"I've opened Explorer for you."`. |
| **C01_web_search_weather** | `PRODUCT_BUG` | **Intent Guard False Positive**: `laya_router.py:270-295` routes weather query to `speech / coder` (`confidence=0.9200`), generating code rather than calling `web_search`. |
| **C02_web_search_stock** | `HARNESS_BUG` | **Stub Signature Mismatch**: `harness_server.py:61` defines `stubbed_web_search(query: str)`. Model emits `{"query": "...", "max_results": "6"}`. Server log: `TypeError: stubbed_web_search() got an unexpected keyword argument 'max_results'`. |
| **C03_web_search_news** | `HARNESS_BUG` | Same as C02: Server log: `TypeError: stubbed_web_search() got an unexpected keyword argument 'max_results'`. |
| **D01_python_palindrome** | `HARNESS_BUG` | **Missing Import**: `runner.py:141` in `parse_python_ast()` calls `re.findall()` without importing `re` at module scope, raising `NameError: name 're' is not defined`. |

---

## 4. Specific Diagnostic Questions

### A. Real Parameter Names in Tool Schemas vs Expected Args (Volume `level` vs `value`)
- In `rufus-backend/app/agent/tools.py` lines 615-635 (`TOOL_DEFINITIONS`):
  ```json
  "parameters": {
      "type": "object",
      "properties": {
          "action": {"type": "string", "enum": ["get", "set", "up", "down", "mute", "unmute"]},
          "level": {"type": "integer", "description": "Target volume percentage (0 to 100) for set..."}
      },
      "required": ["action"]
  }
  ```
  The declared parameter name in the tool schema is **`level`**.
- In `rufus-backend/app/agent/graph.py` lines 427-434 (`tools_node`):
  ```python
  elif tool_name == "system_volume":
      val = tool_args.get("value")
  ```
  `graph.py` inspects **`value`**, NOT **`level`**. Because the model provides `level`, `val` resolves to `None`, causing `graph.py` to format the generic reply: *"I've adjusted the system volume for you."* instead of *"I've set the system volume to 65%."*.

### B. Web Search Stub vs Real Tool Parameters (`max_results`)
- In `rufus-backend/app/agent/tools.py` line 603, the production function is:
  ```python
  def web_search(query: str) -> str:
  ```
- In `benchmarks/e2e/harness_server.py` line 61:
  ```python
  def stubbed_web_search(query: str) -> str:
  ```
  Neither production nor the harness stub defines `max_results`. However, `llama3.2` regularly hallucinates an extra `max_results` parameter (e.g. `{"query": "...", "max_results": "6"}`). Because `stubbed_web_search` lacks `**kwargs`, Python raises `TypeError`, causing tool execution to abort and the model to apologize that the search function failed.

### C. Origin of `open_app` Fallback to Explorer
- In `rufus-backend/app/agent/tools.py` lines 504-518, `open_app` is described as:
  `"Opens an approved desktop application on Windows (WhatsApp, Antigravity, VS Code, Browser/Chrome, File Explorer)."`
- In `rufus-backend/app/agent/graph.py` line 97, `SHARED_TOOL_CAPABILITIES` specifies:
  `"You have access to tools to open discovered desktop applications (WhatsApp, VS Code, Chrome, Brave, Discord, Spotify, Antigravity, Explorer)"`
- `Calculator` is absent from both the prompt capabilities and the tool parameter descriptions.
- When given `"Open calculator"`, `llama3.2` restricts itself to the advertised enum options and chooses `"explorer"`.
- `graph.py` lines 405-412 formats the confirmation using `tool_args.get("app_name")`:
  `mutation_replies.append(f"I've opened {app_name.title()} for you.")` -> *"I've opened Explorer for you."*.

---

## 5. Tool Path Context for `"Hi Rufus!"` & Origin of "WhatsApp background sync is offline"

### Context Received by `agent_node` for `"Hi Rufus!"`
When Laya misroutes `"Hi Rufus!"` to `action_type="action"`, `agent_node` assembles:
1. **System Prompt (`get_system_prompt("companion")`)**:
   ```
   You are Rufus, an embodied AI companion robot dog and desktop assistant. Keep replies voice-friendly: use 1-3 short spoken sentences unless the user explicitly asks for more detail. Do not use markdown, bullet points, headers, or numbered lists because replies will be read aloud through text-to-speech. Ask at most one question per reply. After an action executes, confirm it warmly in one short sentence.

   You have access to tools to open discovered desktop applications (WhatsApp, VS Code, Chrome, Brave, Discord, Spotify, Antigravity, Explorer), send WhatsApp messages, check replies via whatsapp_get_last_interaction, search contacts, save contact numbers, open websites, search the web / define concepts, control Spotify, adjust system volume and brightness, visually inspect the screen with vision AI, and lock the workstation. When the user asks what someone replied or asks about WhatsApp messages, call whatsapp_get_last_interaction. When the user asks about anything on their screen, wants an open app or error inspected, or asks to read from display, you MUST call inspect_screen with their specific question in the query parameter. Never output raw JSON in your spoken reply.

   ### Persistent User & Project Memories:
   - [Preference] Feedback & Tone: Prefers direct, blunt engineering feedback with zero fluff; uses TypeScript and Python.
   - [Project] Rufus Companion Robot: Building ESP32 WROOM-32 dog. Finished ModernBERT router and DDG Lite live search.
   ```
2. **Observed Emotion**:
   `"Current observed user emotion: neutral."`
3. **Memory Rows (`hybrid_memory.get_working_memory()`)**:
   Empty for new test sessions (`e2e_A01_rep1`).
4. **User Message**:
   `"Hi Rufus!"`
5. **Tools Available**:
   Full list of 12 registered tool schemas passed to `litellm.completion()`.

### Origin of `"WhatsApp background sync is offline"`
- In `rufus-backend/app/mcp_servers/whatsapp/tools.py` lines 311-315, `whatsapp_get_last_interaction()` returns:
  ```python
  return (
      f"WhatsApp background sync is offline so I cannot read private messages from disk. "
      f"If WhatsApp is open on your screen, ask me: 'Look at my screen and tell me what {target.title()} replied', "
      f"and I will visually read their reply."
  )
  ```
- In prior test and development runs recorded in `rufus-backend/data/rufus_memory.db` (row 100 of `messages` table, session `test_warmup`), this exact fallback message was generated and stored when testing WhatsApp reading.
- Furthermore, because `SHARED_TOOL_CAPABILITIES` explicitly primes the model:
  `"When the user asks what someone replied or asks about WhatsApp messages, call whatsapp_get_last_interaction... When the user asks about anything on their screen... call inspect_screen"`,
  passing all 12 tools for a simple greeting `"Hi Rufus!"` in `agent_node` causes an **attention leak** in small 3B models (`llama3.2`). The model latches onto the prominent WhatsApp tool descriptions in the prompt and outputs a status statement explaining that WhatsApp sync is offline and offering to inspect the screen.
