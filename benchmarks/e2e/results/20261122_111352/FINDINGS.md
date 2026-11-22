# Rufus E2E Test Suite Findings Report

**Date**: 2026-11-22T11:24:03.359274  
**Total Distinct Queries Tested**: 25  
**Repeats per Query**: 3  
**Temperature**: 0  

---

## Summary of Failures by Severity

### [Severity 1] A03_feeling_tired
- **Input**: `I'm feeling really tired today after a long shift.`
- **Expected**: Path: 1, Tool: NONE, Args: {}
- **Actual**: Path: 2, Tool: system_volume
- **Failed Repeats**: 2/3
- **Sample Reply**: *"I've adjusted the system volume for you."*
- **Root Cause Guess**: LLM emitted tool call despite knowledge-only request (prompt attention leak) *(GUESS)*

### [Severity 1] A05_tell_joke
- **Input**: `Tell me a quick joke to cheer me up.`
- **Expected**: Path: 1, Tool: NONE, Args: {}
- **Actual**: Path: 2, Tool: whatsapp_send_message
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I've sent that message to Mom on WhatsApp."*
- **Root Cause Guess**: LLM emitted tool call despite knowledge-only request (prompt attention leak) *(GUESS)*

### [Severity 1] A08_goodnight
- **Input**: `Goodnight Rufus, going to sleep now.`
- **Expected**: Path: 1, Tool: NONE, Args: {}
- **Actual**: Path: 2, Tool: lock_workstation
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I've locked your workstation."*
- **Root Cause Guess**: LLM emitted tool call despite knowledge-only request (prompt attention leak) *(GUESS)*

### [Severity 2] B01_volume_exact_65
- **Input**: `Set volume to 65%`
- **Expected**: Path: 2, Tool: system_volume, Args: {'level': 65}
- **Actual**: Path: 2, Tool: system_volume
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I've adjusted the system volume for you."*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] B02_volume_exact_40
- **Input**: `Please set the system volume to 40%`
- **Expected**: Path: 2, Tool: system_volume, Args: {'level': 40}
- **Actual**: Path: 2, Tool: system_volume
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I've adjusted the system volume for you."*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] B07_volume_exact_80
- **Input**: `Change volume level to 80 percent`
- **Expected**: Path: 2, Tool: system_volume, Args: {'level': 80}
- **Actual**: Path: 2, Tool: system_volume
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I've adjusted the system volume for you."*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] B08_volume_exact_20
- **Input**: `Turn volume down to 20`
- **Expected**: Path: 2, Tool: system_volume, Args: {'level': 20}
- **Actual**: Path: 2, Tool: system_volume
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I've adjusted the system volume for you."*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] B09_open_calculator
- **Input**: `Open calculator`
- **Expected**: Path: 2, Tool: open_app, Args: {'app_name': 'calculator'}
- **Actual**: Path: 2, Tool: open_app
- **Failed Repeats**: 3/3
- **Sample Reply**: *"I've opened Explorer for you."*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] C01_web_search_weather
- **Input**: `What is the latest weather forecast in Tokyo today?`
- **Expected**: Path: 5, Tool: web_search, Args: {'query': 'Tokyo weather'}
- **Actual**: Path: 1, Tool: NONE
- **Failed Repeats**: 3/3
- **Sample Reply**: *"```typescript import axios from 'axios';  async function getWeatherForecast(city: string) {   try {     const response = await axios.get(`https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=YOUR_API_KEY`);     const weatherData = response.data;     const temperature = weatherData.main.te"*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] C02_web_search_stock
- **Input**: `Search online for current NVIDIA stock price`
- **Expected**: Path: 5, Tool: web_search, Args: {'query': 'NVIDIA stock price'}
- **Actual**: Path: 2, Tool: NONE
- **Failed Repeats**: 3/3
- **Sample Reply**: *"It seems like the web_search function is not working correctly. I'll try to find the latest NVIDIA stock price information for you. Let me check online... [Source](https://www.nvidia.com/investors/financials).  Would you like me to open a website to find the latest stock price?"*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 2] C03_web_search_news
- **Input**: `Look up the latest tech news headlines from today`
- **Expected**: Path: 5, Tool: web_search, Args: {'query': 'tech news'}
- **Actual**: Path: 2, Tool: NONE
- **Failed Repeats**: 3/3
- **Sample Reply**: *"It seems like the web_search function is not working correctly right now. Let me try to find the latest tech news headlines for you instead. Here are the top headlines from today: [Source](https://www.cnet.com/news/)."*
- **Root Cause Guess**: Tool selection or parameter parsing failed in tool schema mapping *(GUESS)*

### [Severity 4] A01_greeting_hi
- **Input**: `Hi Rufus!`
- **Expected**: Path: 1, Tool: NONE, Args: {}
- **Actual**: Path: 2, Tool: NONE
- **Failed Repeats**: 3/3
- **Sample Reply**: *"The WhatsApp background sync is currently offline, which means private messages are not accessible. I'll inspect your screen to see what's visible.  What did WhatsApp say to you?"*
- **Root Cause Guess**: Laya intent router classified query into wrong action_type branch *(GUESS)*

### [Severity 4] A07_thank_you
- **Input**: `Thanks for your help earlier, you did great!`
- **Expected**: Path: 1, Tool: NONE, Args: {}
- **Actual**: Path: 2, Tool: NONE
- **Failed Repeats**: 3/3
- **Sample Reply**: *"The WhatsApp background sync is currently offline, which means private messages are not accessible. I'll check your screen to see what's visible.  What is displayed on your screen?"*
- **Root Cause Guess**: Laya intent router classified query into wrong action_type branch *(GUESS)*

