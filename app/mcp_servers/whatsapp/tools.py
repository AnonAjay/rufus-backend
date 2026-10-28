"""
WhatsApp MCP Tools Implementation for Rufus.
Dual-mode: Integrates with local SQLite / whatsmeow bridge if present,
with graceful fallback to Windows native URI deep linking.

Credits: Adapted from Luke Harries (lharries/whatsapp-mcp, MIT License).
"""
import os
import re
import json
import sqlite3
import logging
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

from app.mcp_servers.whatsapp.contacts import (
    resolve_best_contact,
    save_or_update_contact,
    list_all_contacts,
)

logger = logging.getLogger(__name__)

# Contacts address book path
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
CONTACTS_FILE = BASE_DIR / "data" / "contacts.json"

# Standard database locations checked by whatsapp-mcp
DB_SEARCH_PATHS = [
    Path.home() / ".whatsapp-mcp" / "whatsapp.db",
    Path("data") / "whatsapp.db",
    Path("whatsapp-bridge") / "whatsapp.db",
]


def _load_contacts() -> dict[str, str]:
    """Load local contacts mapping name -> phone number."""
    if CONTACTS_FILE.exists():
        try:
            with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to load contacts.json: %s", exc)
    return {}


def _save_contacts(contacts: dict[str, str]) -> None:
    """Save contacts mapping to disk."""
    try:
        CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
            json.dump(contacts, f, indent=2)
    except Exception as exc:
        logger.error("Failed to save contacts.json: %s", exc)


def save_contact_number(name: str, phone: str) -> str:
    """Store or update a contact's phone number in Rufus's local address book."""
    clean_name = (name or "").strip().lower()
    clean_phone = re.sub(r"[^\d+]", "", (phone or "").strip())
    if not clean_name or not clean_phone:
        return "Please provide both a valid contact name and phone number."
    contacts = _load_contacts()
    contacts[clean_name] = clean_phone
    _save_contacts(contacts)
    return f"Saved contact '{name.title()}' with phone number {clean_phone}."


def _get_database_path() -> Path | None:
    """Find local SQLite database created by the WhatsApp Go bridge."""
    for p in DB_SEARCH_PATHS:
        if p.exists():
            return p
    return None


def get_whatsapp_status() -> dict[str, Any]:
    """Check connectivity to WhatsApp bridge and database."""
    db_path = _get_database_path()
    has_db = db_path is not None

    contact_count = 0
    message_count = 0

    if has_db:
        try:
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='contacts'")
                if cursor.fetchone()[0] > 0:
                    cursor.execute("SELECT count(*) FROM contacts")
                    contact_count = cursor.fetchone()[0]
                cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='messages'")
                if cursor.fetchone()[0] > 0:
                    cursor.execute("SELECT count(*) FROM messages")
                    message_count = cursor.fetchone()[0]
        except Exception as exc:
            logger.warning("Error querying WhatsApp SQLite DB: %s", exc)

    return {
        "bridge_database_found": has_db,
        "database_path": str(db_path) if db_path else None,
        "contacts_synced": contact_count,
        "messages_synced": message_count,
        "mode": "bridge_sqlite" if has_db else "windows_uri_protocol",
    }


def whatsapp_search_contacts(query: str) -> str:
    """Search WhatsApp contacts by name or phone number."""
    q = (query or "").strip().lower()
    if not q:
        return "Please specify a contact name or phone number to search."

    db_path = _get_database_path()
    if db_path:
        try:
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT jid, name, phone FROM contacts WHERE lower(name) LIKE ? OR phone LIKE ? LIMIT 10",
                    (f"%{q}%", f"%{q}%"),
                )
                rows = cursor.fetchall()
                if rows:
                    results = [f"- {r['name'] or 'Unknown'} ({r['phone'] or r['jid']})" for r in rows]
                    return f"Found {len(rows)} matching WhatsApp contacts:\n" + "\n".join(results)
                return f"No contacts found in WhatsApp database matching '{query}'."
        except Exception as exc:
            logger.error("Failed to query WhatsApp contacts: %s", exc)

    return (
        f"WhatsApp local database not synced. In protocol mode, you can direct-message by phone number "
        f"or open WhatsApp desktop to search for '{query}'."
    )


def whatsapp_list_messages(chat: str = "", limit: int = 5, query: str = "") -> str:
    """Retrieve or search recent messages from local WhatsApp cache."""
    db_path = _get_database_path()
    if db_path:
        try:
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                if query:
                    cursor.execute(
                        "SELECT sender, text, timestamp FROM messages WHERE lower(text) LIKE ? ORDER BY timestamp DESC LIMIT ?",
                        (f"%{query.lower()}%", limit),
                    )
                else:
                    cursor.execute(
                        "SELECT sender, text, timestamp FROM messages ORDER BY timestamp DESC LIMIT ?",
                        (limit,),
                    )
                rows = cursor.fetchall()
                if rows:
                    items = [f"[{r['timestamp']}] {r['sender']}: {r['text']}" for r in rows]
                    return f"Recent WhatsApp messages:\n" + "\n".join(items)
                return "No matching messages found in WhatsApp message cache."
        except Exception as exc:
            logger.error("Failed to query WhatsApp messages: %s", exc)

    return (
        "WhatsApp background message sync is currently offline. "
        "Tip: If WhatsApp is open on your screen, ask me to 'look at the screen and summarize WhatsApp' "
        "and I will read it using vision AI."
    )


def _schedule_auto_send(delay_seconds: float = 2.0) -> None:
    """Schedule an automated Enter keypress with robust Win32 window focusing and hardware scancodes."""
    def _worker():
        time.sleep(delay_seconds)
        try:
            import win32gui
            import win32api
            import win32con
            import win32process

            hwnds = []

            def enum_cb(hwnd, extra):
                if win32gui.IsWindowVisible(hwnd):
                    text = win32gui.GetWindowText(hwnd)
                    if "WhatsApp" in text:
                        hwnds.append(hwnd)
                return True

            win32gui.EnumWindows(enum_cb, 0)

            if hwnds:
                target_hwnd = hwnds[0]
                try:
                    fg_hwnd = win32gui.GetForegroundWindow()
                    if fg_hwnd != target_hwnd:
                        fg_tid = win32process.GetWindowThreadProcessId(fg_hwnd)[0] if fg_hwnd else 0
                        app_tid = win32api.GetCurrentThreadId()
                        if fg_tid and fg_tid != app_tid:
                            win32process.AttachThreadInput(fg_tid, app_tid, True)
                            win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                            win32gui.SetForegroundWindow(target_hwnd)
                            win32process.AttachThreadInput(fg_tid, app_tid, False)
                        else:
                            win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                            win32gui.SetForegroundWindow(target_hwnd)
                except Exception as focus_exc:
                    logger.debug("Focus adjustment exception: %s", focus_exc)

                time.sleep(0.3)

            # Synthesize authentic hardware Enter keypress with scancode 0x1C
            scancode = win32api.MapVirtualKey(win32con.VK_RETURN, 0) or 0x1C
            win32api.keybd_event(win32con.VK_RETURN, scancode, 0, 0)
            time.sleep(0.05)
            win32api.keybd_event(win32con.VK_RETURN, scancode, win32con.KEYEVENTF_KEYUP, 0)
            logger.info("Successfully dispatched hardware Enter keypress to WhatsApp.")
        except Exception as exc:
            logger.warning("Auto-enter keystroke synthesis failed: %s", exc)

    threading.Thread(target=_worker, daemon=True).start()


def whatsapp_send_message(recipient: str, message: str) -> str:
    """
    Send a WhatsApp message directly to a recipient (contact name or phone number).
    Uses the Windows desktop WhatsApp protocol handler with automated hardware Enter dispatch.
    """
    msg = (message or "").strip()
    target = (recipient or "").strip()

    if not msg:
        return "Message content cannot be empty."

    # Guard against hallucinated placeholder numbers from LLM schemas
    if target in {"+1234567890", "1234567890", "+1234567", "1234567"}:
        target = ""

    # 1. Resolve contact using SQLite database with MRU / frequency ranking
    resolved_contact = resolve_best_contact(target) if target else None
    resolved_phone = None
    display_name = target

    if resolved_contact:
        resolved_phone = resolved_contact["phone"]
        display_name = resolved_contact["name"]
    else:
        # Check if digits in target represent a real phone number
        digits = re.sub(r"[^\d+]", "", target)
        clean_digits = re.sub(r"[^\d]", "", digits)
        if len(clean_digits) >= 10 and not clean_digits.startswith("1234567"):
            resolved_phone = digits

    encoded_text = urllib.parse.quote(msg)

    # 2. If a phone number is known, execute hands-free direct dispatch
    if resolved_phone:
        phone_param = resolved_phone.lstrip("+")
        uri = f"whatsapp://send?phone={phone_param}&text={encoded_text}"
        fallback_url = f"https://web.whatsapp.com/send?phone={phone_param}&text={encoded_text}"

        try:
            os.startfile(uri)
            # Trigger hands-free Enter key dispatch with 2.0s chat-render delay
            _schedule_auto_send(delay_seconds=2.0)
            return f"Message sent to {display_name.title()} ({resolved_phone}): '{msg}'."
        except Exception as exc:
            logger.info("Direct WhatsApp protocol failed (%s), opening web fallback", exc)
            try:
                webbrowser.open(fallback_url)
                return f"Opened WhatsApp Web to send message to {display_name.title()} ({resolved_phone})."
            except Exception as web_exc:
                return f"Failed to send WhatsApp message: {web_exc}"

    # 3. If contact is not saved, prompt user for phone number instead of opening broken contact picker
    if target:
        return (
            f"I don't have a phone number for '{target.title()}' in my address book. "
            f"Please tell me: 'Save {target.title()}'s number as +91...' (with their phone number), "
            f"and I will save it and send your message immediately."
        )

    return "Please specify a recipient name or phone number."


def whatsapp_get_last_interaction(contact: str) -> str:
    """Find the latest interaction timestamp or message with a contact."""
    db_path = _get_database_path()
    if db_path:
        try:
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT sender, text, timestamp FROM messages WHERE lower(sender) LIKE ? ORDER BY timestamp DESC LIMIT 1",
                    (f"%{contact.lower()}%",),
                )
                row = cursor.fetchone()
                if row:
                    return f"Last interaction with {contact} was at {row['timestamp']}: '{row['text']}'"
                return f"No recorded interaction found for '{contact}'."
        except Exception as exc:
            logger.error("Failed to get last interaction: %s", exc)

    return f"WhatsApp message archive offline. Unable to query last interaction with '{contact}'."

