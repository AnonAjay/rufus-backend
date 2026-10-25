import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DB_DIR / "rufus_memory.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Try loading sqlite-vec extension if installed
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception as exc:
        logger.debug("sqlite-vec extension not loaded (will use fallback): %s", exc)

    return conn


def init_hybrid_database() -> None:
    """Initialize SQLite tables for tiered memory (Working Memory, Episodic Summaries, FTS5)."""
    conn = _get_connection()
    try:
        with conn:
            # 1. Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    synced INTEGER DEFAULT 0
                )
            """)

            # 2. Verbatim messages table (Working Memory Buffer & Full History)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    text TEXT NOT NULL,
                    actions TEXT,
                    model_used TEXT,
                    accuracy TEXT,
                    timestamp TEXT NOT NULL,
                    synced INTEGER DEFAULT 0,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # Index for fast session query
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session_id 
                ON messages(session_id, timestamp)
            """)

            # 3. Episodic Summaries table (Tier 2 - Rolling Condensed Memory)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodic_summaries (
                    session_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    turn_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # 4. FTS5 Virtual Table for Sparse BM25 Keyword Search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                    message_id UNINDEXED,
                    session_id UNINDEXED,
                    text,
                    tokenize='porter'
                )
            """)

            # 5. Embedding Archive (Fallback BLOB storage for vectors)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS message_embeddings (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE
                )
            """)

        logger.info("Local Rufus hybrid memory database initialized at %s", DB_PATH)
    finally:
        conn.close()


class HybridMemoryManager:
    """Manages the 3-Tier Memory Architecture:
    1. Working Memory (Verbatim 8-10 turns for active LLM context).
    2. Episodic Memory (Rolling entity/fact summaries).
    3. Semantic Archive (FTS5 BM25 + Vector Embeddings).
    """

    def __init__(self) -> None:
        init_hybrid_database()

    def ensure_session(self, session_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Ensure a session exists; create if missing."""
        conn = _get_connection()
        now = _now_iso()
        try:
            with conn:
                row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
                if row:
                    return dict(row)

                session_title = title or "New Conversation"
                conn.execute(
                    "INSERT INTO sessions (id, title, created_at, updated_at, synced) VALUES (?, ?, ?, ?, 0)",
                    (session_id, session_title, now, now),
                )
                return {
                    "id": session_id,
                    "title": session_title,
                    "created_at": now,
                    "updated_at": now,
                    "synced": 0,
                }
        finally:
            conn.close()

    def update_session_title(self, session_id: str, title: str) -> None:
        conn = _get_connection()
        try:
            with conn:
                conn.execute(
                    "UPDATE sessions SET title = ?, updated_at = ?, synced = 0 WHERE id = ?",
                    (title, _now_iso(), session_id),
                )
        finally:
            conn.close()

    def save_turn(
        self,
        session_id: str,
        user_text: str,
        assistant_reply: str,
        actions: Optional[List[str]] = None,
        model_used: Optional[str] = None,
        accuracy: Optional[str] = None,
    ) -> None:
        """Atomically persist a complete conversational turn (User Prompt + Rufus Reply)."""
        conn = _get_connection()
        now = _now_iso()
        user_msg_id = f"user-{uuid.uuid4().hex[:12]}"
        asst_msg_id = f"asst-{uuid.uuid4().hex[:12]}"
        actions_json = json.dumps(actions or [])

        # Auto-title generation from first user prompt if still default
        self.ensure_session(session_id)

        try:
            with conn:
                # Check if session needs a real title
                session_row = conn.execute("SELECT title FROM sessions WHERE id = ?", (session_id,)).fetchone()
                if session_row and session_row["title"] == "New Conversation":
                    # Generate concise 5-8 word title from user prompt
                    words = user_text.strip().split()
                    new_title = " ".join(words[:6]).capitalize()
                    if len(words) > 6:
                        new_title += "..."
                    conn.execute(
                        "UPDATE sessions SET title = ?, updated_at = ?, synced = 0 WHERE id = ?",
                        (new_title, now, session_id),
                    )
                else:
                    conn.execute(
                        "UPDATE sessions SET updated_at = ?, synced = 0 WHERE id = ?",
                        (now, session_id),
                    )

                # Insert user message
                conn.execute(
                    """
                    INSERT INTO messages (id, session_id, sender, text, actions, model_used, accuracy, timestamp, synced)
                    VALUES (?, ?, 'user', ?, NULL, NULL, NULL, ?, 0)
                    """,
                    (user_msg_id, session_id, user_text, now),
                )

                # Insert assistant reply
                conn.execute(
                    """
                    INSERT INTO messages (id, session_id, sender, text, actions, model_used, accuracy, timestamp, synced)
                    VALUES (?, ?, 'assistant', ?, ?, ?, ?, ?, 0)
                    """,
                    (asst_msg_id, session_id, assistant_reply, actions_json, model_used, accuracy, now),
                )

                # Index both messages in FTS5
                conn.execute(
                    "INSERT INTO messages_fts (message_id, session_id, text) VALUES (?, ?, ?)",
                    (user_msg_id, session_id, user_text),
                )
                conn.execute(
                    "INSERT INTO messages_fts (message_id, session_id, text) VALUES (?, ?, ?)",
                    (asst_msg_id, session_id, assistant_reply),
                )

            logger.info("Persisted turn for session %s to local SQLite.", session_id)
        finally:
            conn.close()

    def get_working_memory(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """Fetch the verbatim Working Memory Buffer (last 8-10 turns) for LLM context."""
        conn = _get_connection()
        try:
            # Query last N messages
            rows = conn.execute(
                """
                SELECT sender, text FROM messages
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()

            # Reverse so chronological order (oldest to newest)
            messages = [{"role": r["sender"], "content": r["text"]} for r in reversed(rows)]
            return messages
        finally:
            conn.close()

    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Fetch full chronological turns for UI rendering."""
        conn = _get_connection()
        try:
            rows = conn.execute(
                """
                SELECT id, session_id, sender, text, actions, model_used, accuracy, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (session_id,),
            ).fetchall()

            result = []
            for r in rows:
                actions = []
                if r["actions"]:
                    try:
                        actions = json.loads(r["actions"])
                    except Exception:
                        actions = []
                result.append({
                    "id": r["id"],
                    "sessionId": r["session_id"],
                    "sender": r["sender"],
                    "text": r["text"],
                    "actions": actions,
                    "modelUsed": r["model_used"],
                    "accuracy": r["accuracy"],
                    "timestamp": r["timestamp"],
                })
            return result
        finally:
            conn.close()

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch session list with message counts and last message preview for the History tab."""
        conn = _get_connection()
        try:
            query = """
                SELECT 
                    s.id,
                    s.title,
                    s.created_at,
                    s.updated_at,
                    s.synced,
                    COUNT(m.id) as message_count,
                    (SELECT text FROM messages WHERE session_id = s.id ORDER BY timestamp DESC LIMIT 1) as last_message,
                    (SELECT model_used FROM messages WHERE session_id = s.id AND model_used IS NOT NULL ORDER BY timestamp DESC LIMIT 1) as last_model
                FROM sessions s
                LEFT JOIN messages m ON s.id = m.session_id
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                LIMIT ?
            """
            rows = conn.execute(query, (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> bool:
        """Delete session and associated messages."""
        conn = _get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM messages_fts WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM episodic_summaries WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return True
        finally:
            conn.close()

    def search_keyword(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Sparse BM25 full-text search across all message archives via FTS5."""
        conn = _get_connection()
        try:
            # Escape FTS special syntax
            safe_query = "".join(c for c in query if c.isalnum() or c.isspace()).strip()
            if not safe_query:
                return []

            sql = """
                SELECT m.id, m.session_id, m.sender, m.text, m.timestamp, s.title as session_title
                FROM messages_fts f
                JOIN messages m ON f.message_id = m.id
                JOIN sessions s ON m.session_id = s.id
                WHERE messages_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            rows = conn.execute(sql, (f"{safe_query}*", limit)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# Global Singleton Instance
hybrid_memory = HybridMemoryManager()
