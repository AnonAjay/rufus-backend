import sqlite3
import json
import urllib.request

conn = sqlite3.connect("rufus-backend/data/rufus_memory.db")
c = conn.cursor()
c.execute("SELECT sender, text FROM messages WHERE session_id = '6259b028-16cc-45ce-83ee-9b045e57a3a6' ORDER BY rowid ASC")
rows = c.fetchall()

messages = [{"role": "system", "content": "You are Rufus, an expert software engineer and technical architect. Prioritize clean, idiomatic, robust code. Lead with the complete, production-ready code block FIRST in standard markdown code fences (e.g. ```python, ```rust, ```typescript). After the code block, explain design decisions, complexity, and edge cases."}]

# Take the last 6 messages (which are poisoned)
for sender, text in rows[-6:]:
    role = "assistant" if sender == "assistant" else "user"
    messages.append({"role": role, "content": text})

print(f"Total messages in test prompt: {len(messages)}")
print("Last message sent to model:", messages[-1])
