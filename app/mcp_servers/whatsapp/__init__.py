"""
WhatsApp MCP Tools Package for Rufus.
Credits: Adapted from Luke Harries (lharries/whatsapp-mcp, MIT License).
"""
from app.mcp_servers.whatsapp.tools import (
    get_whatsapp_status,
    whatsapp_get_last_interaction,
    whatsapp_list_messages,
    whatsapp_search_contacts,
    whatsapp_send_message,
    save_contact_number,
)

__all__ = [
    "whatsapp_send_message",
    "whatsapp_search_contacts",
    "whatsapp_list_messages",
    "whatsapp_get_last_interaction",
    "get_whatsapp_status",
    "save_contact_number",
]
