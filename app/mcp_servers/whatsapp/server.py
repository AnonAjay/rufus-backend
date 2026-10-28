"""
Standalone WhatsApp MCP Server for Rufus.
Can be executed as a standard MCP server via stdio by any MCP-compliant client.
Credits: Adapted from Luke Harries (lharries/whatsapp-mcp, MIT License).
"""
import sys
from mcp.server.fastmcp import FastMCP

from app.mcp_servers.whatsapp.tools import (
    get_whatsapp_status,
    whatsapp_get_last_interaction,
    whatsapp_list_messages,
    whatsapp_search_contacts,
    whatsapp_send_message,
)

mcp = FastMCP("whatsapp-mcp")


@mcp.tool()
def search_contacts(query: str) -> str:
    """Search WhatsApp contacts by name or phone number."""
    return whatsapp_search_contacts(query)


@mcp.tool()
def list_messages(chat: str = "", limit: int = 5, query: str = "") -> str:
    """Retrieve or search recent messages from local WhatsApp cache."""
    return whatsapp_list_messages(chat=chat, limit=limit, query=query)


@mcp.tool()
def send_message(recipient: str, message: str) -> str:
    """Send or prepare a WhatsApp message to a contact name or phone number."""
    return whatsapp_send_message(recipient=recipient, message=message)


@mcp.tool()
def get_last_interaction(contact: str) -> str:
    """Find the latest interaction timestamp or message exchanged with a contact."""
    return whatsapp_get_last_interaction(contact)


@mcp.tool()
def get_status() -> dict:
    """Check connectivity to WhatsApp bridge and database."""
    return get_whatsapp_status()


if __name__ == "__main__":
    mcp.run()

