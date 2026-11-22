"""
Read-only inspection script: lists e2e_* sessions and suspicious stale messages in rufus_memory.db.
Strictly read-only; never deletes or modifies any records.
"""
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "rufus_memory.db"

def main():
    if not DB_PATH.exists():
        print(f"Memory database not found at {DB_PATH}")
        return

    print(f"Inspecting database (READ-ONLY): {DB_PATH}")
    # Read-only URI mode
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    c = conn.cursor()

    print("\n" + "=" * 80)
    print("1. TEST / BENCHMARK SESSIONS (matching e2e_%, test_%, warmup_%, benchmark-%)")
    print("=" * 80)
    c.execute("""
        SELECT session_id, count(*), min(timestamp), max(timestamp)
        FROM messages
        WHERE session_id LIKE 'e2e_%'
           OR session_id LIKE 'test_%'
           OR session_id LIKE 'warmup_%'
           OR session_id LIKE 'benchmark-%'
        GROUP BY session_id
        ORDER BY min(timestamp) ASC;
    """)
    rows = c.fetchall()
    if not rows:
        print("No test/benchmark sessions found in messages table.")
    else:
        for sid, cnt, t_start, t_end in rows:
            print(f"  Session: {sid:<35} | Turns: {cnt:<3} | Range: {t_start} -> {t_end}")

    print("\n" + "=" * 80)
    print("2. SUSPICIOUS / STALE MESSAGES (containing 'sync', 'offline', 'mock', 'stub')")
    print("=" * 80)
    c.execute("""
        SELECT rowid, id, session_id, sender, text, timestamp
        FROM messages
        WHERE text LIKE '%background sync%'
           OR text LIKE '%sync is offline%'
           OR text LIKE '%[STUB]%'
           OR text LIKE '%mocked for safety%'
        ORDER BY rowid ASC;
    """)
    suspicious = c.fetchall()
    if not suspicious:
        print("No suspicious stale messages detected.")
    else:
        for rowid, mid, sid, sender, text, ts in suspicious:
            clean_text = text.replace('\r', ' ').replace('\n', ' ')[:100]
            print(f"  Row {rowid:<4} | Session: {sid:<25} | Sender: {sender:<10} | Text: \"{clean_text}...\"")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total matching sessions: {len(rows)}")
    print(f"Total suspicious messages: {len(suspicious)}")
    print("Note: As per Rule 5, no rows have been deleted or modified. Review above.")

    conn.close()

if __name__ == "__main__":
    main()
