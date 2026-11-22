# Rufus E2E Test Suite Findings Report

**Date**: 2026-11-22T18:38:50.517901  
**Total Distinct Queries Tested**: 25  
**Repeats per Query**: 3  
**Temperature**: 0  

---

## Summary of Failures by Severity

### [Severity 1] A01_greeting_hi
- **Input**: `Hi Rufus!`
- **Expected**: Path: 1, Tool: NONE, Args: {}
- **Actual**: Path: 2, Tool: open_app
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I've opened Whatsapp for you."*
- **Root Cause Guess**: LLM emitted tool call despite knowledge-only request (prompt attention leak) *(GUESS)*

### [Severity 1] A02_greeting_good_morning
- **Input**: `Good morning, how are you doing today?`
- **Expected**: Path: 1, Tool: NONE, Args: {}
- **Actual**: Path: 2, Tool: NONE
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I'm doing well, thanks for asking."*
- **Root Cause Guess**: LLM emitted tool call despite knowledge-only request (prompt attention leak) *(GUESS)*

### [Severity 1] A03_feeling_tired
- **Input**: `I'm feeling really tired today after a long shift.`
- **Expected**: Path: 1, Tool: NONE, Args: {}
- **Actual**: Path: 2, Tool: whatsapp_send_message
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I've sent that message to Mom on WhatsApp."*
- **Root Cause Guess**: LLM emitted tool call despite knowledge-only request (prompt attention leak) *(GUESS)*

### [Severity 1] A05_tell_joke
- **Input**: `Tell me a quick joke to cheer me up.`
- **Expected**: Path: 1, Tool: NONE, Args: {}
- **Actual**: Path: 2, Tool: whatsapp_send_message
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I've sent that message to Rufus Robot on WhatsApp."*
- **Root Cause Guess**: LLM emitted tool call despite knowledge-only request (prompt attention leak) *(GUESS)*

### [Severity 1] A07_thank_you
- **Input**: `Thanks for your help earlier, you did great!`
- **Expected**: Path: 1, Tool: NONE, Args: {}
- **Actual**: Path: 2, Tool: open_app
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I've opened Whatsapp for you."*
- **Root Cause Guess**: LLM emitted tool call despite knowledge-only request (prompt attention leak) *(GUESS)*

### [Severity 1] A08_goodnight
- **Input**: `Goodnight Rufus, going to sleep now.`
- **Expected**: Path: 1, Tool: NONE, Args: {}
- **Actual**: Path: 2, Tool: lock_workstation
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I've locked your workstation."*
- **Root Cause Guess**: LLM emitted tool call despite knowledge-only request (prompt attention leak) *(GUESS)*

### [Severity 2] B06_volume_hinglish_badha
- **Input**: `Volume thoda badha do`
- **Expected**: Path: 2, Tool: system_volume, Args: {'action': 'up'}
- **Actual**: Path: 2, Tool: system_volume
- **Failed Repeats**: 1/3
- **Sample Reply**: *"I've adjusted the system volume for you."*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] B09_open_calculator
- **Input**: `Open calculator`
- **Expected**: Path: 2, Tool: open_app, Args: {'app_name': 'calculator'}
- **Actual**: Path: 2, Tool: open_app
- **Failed Repeats**: 2/3
- **Sample Reply**: *"I've opened Explorer for you."*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] B10_launch_notepad
- **Input**: `Launch notepad for me`
- **Expected**: Path: 2, Tool: open_app, Args: {'app_name': 'notepad'}
- **Actual**: Path: 2, Tool: open_app
- **Failed Repeats**: 1/3
- **Sample Reply**: *"I've opened Explorer for you."*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] C01_web_search_weather
- **Input**: `What is the latest weather forecast in Tokyo today?`
- **Expected**: Path: 5, Tool: web_search, Args: {'query': 'Tokyo weather'}
- **Actual**: Path: 1, Tool: NONE
- **Failed Repeats**: 3/3
- **Sample Reply**: *"```python import requests  def get_weather_forecast(city, query):     url = "https://api.openweathermap.org/forecast?q=""*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

