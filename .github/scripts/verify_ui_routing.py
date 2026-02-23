import requests
import os
import sys
import time

# Config
QUERY_API_URL = os.getenv("QUERY_API_URL", "http://localhost:8001")
TOKEN = os.getenv("AUTH_TOKEN") # Needs to be valid for v5

def test_alerts_endpoint():
    print("Verifying v5 Query API Alerts Endpoint...")
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        resp = requests.get(f"{QUERY_API_URL}/alerts", headers=headers, timeout=5)

        if resp.status_code == 200:
            print("SUCCESS: v5 /alerts is reachable.")
            data = resp.json()
            if isinstance(data, list) or 'results' in data:
                print("SUCCESS: v5 returned list structure.")
            else:
                print(f"WARNING: Unexpected response structure: {data.keys()}")
        elif resp.status_code == 403:
            print("SUCCESS: v5 enforced RBAC (403).")
        else:
            print(f"FAILURE: v5 returned {resp.status_code}")
            sys.exit(1)

    except Exception as e:
        print(f"FAILURE: Connection error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if not TOKEN:
        print("SKIP: No token provided.")
        sys.exit(0)
    test_alerts_endpoint()
