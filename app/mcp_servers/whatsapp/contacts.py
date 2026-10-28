"""
SQLite Contacts Store & Cache for WhatsApp MCP.
Supports exact matching, fuzzy search, and MRU (Most Recently / Frequently Used)
priority ranking for contact disambiguation.
"""
import re
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = BASE_DIR / "data" / "whatsapp.db"


def _init_db() -> None:
    """Initialize the contacts table in data/whatsapp.db."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                jid TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                interaction_count INTEGER DEFAULT 1,
                last_interacted_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone)")


def save_or_update_contact(name: str, phone: str, jid: str | None = None) -> dict[str, Any]:
    """Upsert a contact into the SQLite database."""
    _init_db()
    clean_name = (name or "").strip()
    clean_phone = re.sub(r"[^\d+]", "", (phone or "").strip())
    if not clean_phone.startswith("+") and len(clean_phone) == 10:
        clean_phone = "+91" + clean_phone  # Standard default if 10-digit mobile

    contact_jid = jid or f"{clean_phone.lstrip('+')}@s.whatsapp.net"
    now_iso = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT jid, interaction_count FROM contacts WHERE phone = ? OR lower(name) = ?", (clean_phone, clean_name.lower()))
        row = cur.fetchone()

        if row:
            target_jid = row["jid"]
            new_count = row["interaction_count"] + 1
            conn.execute(
                "UPDATE contacts SET name = ?, phone = ?, interaction_count = ?, last_interacted_at = ? WHERE jid = ?",
                (clean_name, clean_phone, new_count, now_iso, target_jid),
            )
        else:
            conn.execute(
                "INSERT INTO contacts (jid, name, phone, interaction_count, last_interacted_at) VALUES (?, ?, ?, 1, ?)",
                (contact_jid, clean_name, clean_phone, now_iso),
            )

    return {
        "jid": contact_jid,
        "name": clean_name,
        "phone": clean_phone,
    }


def resolve_best_contact(query: str) -> dict[str, Any] | None:
    """
    Search for a contact by name or phone.
    If multiple contacts match, applies MRU / Frequency caching (sorting by interaction_count DESC,
    last_interacted_at DESC) to select the most likely contact.
    """
    _init_db()
    q = (query or "").strip().lower()
    if not q:
        return None

    # Check if query itself is an explicit phone number
    digits = re.sub(r"[^\d+]", "", q)
    if len(re.sub(r"[^\d]", "", digits)) >= 10:
        return {
            "name": query,
            "phone": digits,
            "jid": f"{digits.lstrip('+')}@s.whatsapp.net",
        }

    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 1. Exact name match (highest priority)
        cur.execute(
            "SELECT jid, name, phone, interaction_count, last_interacted_at FROM contacts WHERE lower(name) = ? ORDER BY interaction_count DESC, last_interacted_at DESC",
            (q,),
        )
        exact_rows = cur.fetchall()
        if exact_rows:
            best = dict(exact_rows[0])
            _bump_interaction(best["jid"])
            return best

        # 2. Substring / fuzzy name match (ranked by MRU / frequency)
        cur.execute(
            "SELECT jid, name, phone, interaction_count, last_interacted_at FROM contacts WHERE lower(name) LIKE ? OR phone LIKE ? ORDER BY interaction_count DESC, last_interacted_at DESC LIMIT 5",
            (f"%{q}%", f"%{q}%"),
        )
        fuzzy_rows = cur.fetchall()
        if fuzzy_rows:
            best = dict(fuzzy_rows[0])
            _bump_interaction(best["jid"])
            return best

    return None


def _bump_interaction(jid: str) -> None:
    """Increment interaction count and update last_interacted_at (MRU/Redis-style cache update)."""
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute(
                "UPDATE contacts SET interaction_count = interaction_count + 1, last_interacted_at = ? WHERE jid = ?",
                (now_iso, jid),
            )
    except Exception as exc:
        logger.warning("Failed to bump contact interaction count: %s", exc)


def list_all_contacts(limit: int = 50) -> list[dict[str, Any]]:
    """Return all stored contacts sorted by recency and frequency."""
    _init_db()
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT jid, name, phone, interaction_count, last_interacted_at FROM contacts ORDER BY interaction_count DESC, last_interacted_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]

