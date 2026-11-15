import sys
import os
import json
import urllib.request

# Ensure rufus-backend root is in python path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

def main():
    query = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "Can you give me code for writing a palindrome and printing the palindrome in Python?"
    )

    print("=" * 70)
    print("STEP 1: LAYA INTENT CLASSIFICATION")
    print("=" * 70)
    try:
        from app.agent.laya_router import classify_intent
        res = classify_intent(query)
        print(f"Query: \"{query}\"")
        print(f"Action Type: {res.get('action_type')}")
        print(f"Persona Intent: {res.get('persona_intent')}")
        print(f"Confidence: {res.get('confidence'):.3f}")
        print(f"Source: {res.get('source')}")
    except Exception as e:
        print(f"Laya import or classification error: {e}")

    print("\n" + "=" * 70)
    print("STEP 2: END-TO-END FASTAPI CHAT ENDPOINT (http://127.0.0.1:8000/agent/chat)")
    print("=" * 70)
    payload = {
        "session_id": "cli-debug-session",
        "message": query,
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/agent/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            reply = data.get("reply", "")
            actions = data.get("actions", [])
            model = data.get("model_used", "unknown")

            print(f"HTTP Status: {resp.status}")
            print(f"Model Used: {model}")
            print(f"Actions Executed: {actions}")
            print(f"Contains Markdown Code Fences: {'```' in reply}")
            print("-" * 70)
            print("REPLY PAYLOAD DELIVERED TO FRONTEND:")
            print(reply)
            print("=" * 70)
    except urllib.error.URLError as e:
        print(f"Failed to connect to Uvicorn at http://127.0.0.1:8000: {e}")
        print("Ensure `uvicorn app.main:app --reload` is running in your backend terminal.")
    except Exception as e:
        print(f"Request error: {e}")

if __name__ == "__main__":
    main()
