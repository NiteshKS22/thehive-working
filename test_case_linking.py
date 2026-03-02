import os
import sys
import requests
import json
import time

API_BASE_QUERY = "http://localhost:8000"
API_BASE_ENGINE = "http://localhost:8082"

def get_token():
    resp = requests.post(f"{API_BASE_QUERY}/login", json={"user": "admin", "password": "admin"})
    if resp.status_code != 200:
        print("Login failed:", resp.text)
        sys.exit(1)
    return resp.json()["token"]

def main():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": f"test-{time.time()}"}

    print("--- 1. Testing Case Linking ---")
    # Create Case A
    resp_a = requests.post(f"{API_BASE_ENGINE}/cases", json={"title": "Case A", "severity": 2}, headers=headers)
    case_a_id = resp_a.json()["case_id"]
    print(f"Created Case A: {case_a_id}")

    # Create Case B
    headers["Idempotency-Key"] = f"test-{time.time()}-b"
    resp_b = requests.post(f"{API_BASE_ENGINE}/cases", json={"title": "Case B", "severity": 3}, headers=headers)
    case_b_id = resp_b.json()["case_id"]
    print(f"Created Case B: {case_b_id}")

    # Link Case A to Case B
    resp_link = requests.post(f"{API_BASE_ENGINE}/cases/{case_a_id}/links", json={"target_case_id": case_b_id}, headers=headers)
    print(f"Link Status Code: {resp_link.status_code}")

    # Read Links (via standard nv-query endpoint)
    resp_get_links = requests.get(f"{API_BASE_QUERY}/cases/{case_a_id}/links", headers=headers)
    print(f"Links for Case A: {json.dumps(resp_get_links.json(), indent=2)}")

    print("\n--- 2. Testing Private Cases ---")
    headers["Idempotency-Key"] = f"test-{time.time()}-priv"
    resp_priv = requests.post(
        f"{API_BASE_ENGINE}/cases", 
        json={"title": "Top Secret Case", "visibility": "PRIVATE", "permitted_users": ["admin@neuralvyuha.local"]}, 
        headers=headers
    )
    case_priv_id = resp_priv.json()["case_id"]
    print(f"Created Private Case: {case_priv_id}")

    # Read the Private Case
    resp_get_priv = requests.get(f"{API_BASE_QUERY}/cases/{case_priv_id}", headers=headers)
    print(f"Read Private Case Details:\n{json.dumps(resp_get_priv.json(), indent=2)}")
    
if __name__ == "__main__":
    main()
