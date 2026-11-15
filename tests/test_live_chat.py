import sys
import json
import urllib.request
import time

def main():
    message = sys.argv[1] if len(sys.argv) > 1 else "Lock my workstation"
    print(f"Testing live /agent/chat with query: '{message}'...")

    payload = {
        "session_id": "fast-action-test",
        "message": message,
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/agent/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            elapsed = time.time() - t0
            data = json.loads(resp.read().decode("utf-8"))
            print("=" * 60)
            print(f"STATUS: {resp.status} (Elapsed: {elapsed:.2f}s)")
            print(f"ACTIONS: {data.get('actions')}")
            print(f"MODEL: {data.get('model_used')}")
            print(f"CONFIDENCE: {data.get('confidence')}")
            print(f"REPLY: {data.get('reply')}")
            print("=" * 60)
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    main()
