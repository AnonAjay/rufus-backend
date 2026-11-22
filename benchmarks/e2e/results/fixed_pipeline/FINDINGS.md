# Rufus E2E Test Suite Findings Report

**Date**: 2026-11-22T21:46:05.422911  
**Total Distinct Queries Tested**: 25  
**Repeats per Query**: 3  
**Temperature**: 0  

---

## Summary of Failures by Severity

### [Severity 2] B03_volume_mute
- **Input**: `Mute the volume`
- **Expected**: Path: 2, Tool: system_volume, Args: {'action': 'mute'}
- **Actual**: Path: 2, Tool: NONE
- **Failed Repeats**: 1/3
- **Sample Reply**: *"Could you please specify the volume level as a number between 0 and 100?"*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] B04_volume_unmute
- **Input**: `Unmute the system sound`
- **Expected**: Path: 2, Tool: system_volume, Args: {'action': 'unmute'}
- **Actual**: Path: 2, Tool: NONE
- **Failed Repeats**: 1/3
- **Sample Reply**: *"Could you please specify the volume level as a number between 0 and 100?"*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] B07_volume_exact_80
- **Input**: `Change volume level to 80 percent`
- **Expected**: Path: 2, Tool: system_volume, Args: {'level': 80}
- **Actual**: Path: 1, Tool: NONE
- **Failed Repeats**: 3/3
- **Sample Reply**: *"Confirming volume level adjustment to 80 percent. Is that to your preferred listening level?"*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] C01_web_search_weather
- **Input**: `What is the latest weather forecast in Tokyo today?`
- **Expected**: Path: 5, Tool: web_search, Args: {'query': 'Tokyo weather'}
- **Actual**: Path: 1, Tool: NONE
- **Failed Repeats**: 3/3
- **Sample Reply**: *"```typescript // Note: This is a simplified example and does not use a real weather API. // In a production environment,"*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] C04_screen_inspect_active
- **Input**: `What is currently open on my screen right now?`
- **Expected**: Path: 5, Tool: inspect_screen, Args: {}
- **Actual**: Path: 2, Tool: NONE
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I've handled that for you."*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

