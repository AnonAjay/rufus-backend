# WhatsApp MCP Server for Rufus

This module provides the **Model Context Protocol (MCP)** tools for interacting with WhatsApp from within Rufus Desktop and Rufus Backend.

## Credits & Attribution

This integration is adapted from and inspired by the open-source **[whatsapp-mcp](https://github.com/lharries/whatsapp-mcp)** project created by **[Luke Harries](https://github.com/lharries)** (MIT License).

- **Original Repository:** `https://github.com/lharries/whatsapp-mcp`
- **Original Author:** Luke Harries
- **License:** MIT License

We express our gratitude to Luke Harries and the community for pioneering the WhatsApp Model Context Protocol architecture.

---

## Architecture & Dual-Mode Execution

1. **Full Bridge Mode (whatsmeow / SQLite):**
   - Communicates with the local `whatsapp-bridge` daemon (built with Go and `whatsmeow`).
   - Reads incoming and historical messages from local SQLite storage (`whatsapp.db`).
   - Queries contacts, chat threads, and interaction history.

2. **Native Windows Protocol Fallback (Zero-Dependency Mode):**
   - If the background Go bridge is not running, the module gracefully falls back to Windows native `whatsapp://send?phone=...&text=...` deep-linking.
   - Launches the desktop WhatsApp application and prepares the message for the user without dropping the request or raising unhandled exceptions.

---

## Exposed MCP Tools

- `whatsapp_send_message(recipient: str, message: str)`: Sends a message to a contact name or phone number.
- `whatsapp_search_contacts(query: str)`: Searches local WhatsApp contacts by name or phone.
- `whatsapp_list_messages(chat_jid: str, limit: int, query: str)`: Lists recent messages from a chat.
- `whatsapp_get_last_interaction(contact: str)`: Retrieves the most recent exchange with a contact.
- `whatsapp_get_status()`: Reports connection status of the WhatsApp bridge.

