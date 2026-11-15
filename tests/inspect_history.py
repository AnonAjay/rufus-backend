import sqlite3

conn = sqlite3.connect("rufus-backend/data/rufus_memory.db")
c = conn.cursor()
c.execute("SELECT id, sender, text FROM messages WHERE session_id = '6259b028-16cc-45ce-83ee-9b045e57a3a6' ORDER BY rowid ASC")
rows = c.fetchall()
print(f"Total messages in session: {len(rows)}")
for i, r in enumerate(rows):
    print(f"--- [{i}] {r[1]} ({r[0]}) ---")
    print(r[2][:150] + ("..." if len(r[2]) > 150 else ""))
