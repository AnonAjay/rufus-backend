import sqlite3
import sys

def main():
    db_path = "rufus-backend/data/rufus_memory.db"
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
            SELECT id, session_id, sender, text, actions, model_used, timestamp 
            FROM messages 
            ORDER BY rowid DESC 
            LIMIT 2
        """)
        rows = c.fetchall()
        if not rows:
            print("No messages found in database.")
            return

        for r in reversed(rows):
            msg_id, session_id, sender, text, actions, model, ts = r
            print("=" * 70)
            print(f"[{sender.upper()}] ID: {msg_id} | TIME: {ts}")
            print(f"Session: {session_id} | Model: {model} | Actions: {actions}")
            print("-" * 70)
            print("BODY:")
            print(text)
            has_fence = "```" in text
            print("-" * 70)
            print(f"Contains Markdown Code Fence (```): {has_fence}")
        print("=" * 70)
    except Exception as e:
        print(f"Failed to inspect SQLite database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
