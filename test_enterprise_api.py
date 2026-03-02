import requests
import json
import time

BASE_URL = "http://localhost:8000"  # nv-query port
HEADERS = {
    "Authorization": "Bearer fake-token-for-dev",
    "Content-Type": "application/json"
}

def print_result(step, response):
    status = "SUCCESS" if response.status_code in [200, 201] else f"FAILED ({response.status_code})"
    print(f"[{status}] {step}")
    if status.startswith("FAILED"):
        print(f"  Response: {response.text}")
    return response.status_code in [200, 201]

def run_verification():
    print("--- Enterprise Case Verification Suite ---")

    # 1. Create Case
    payload = {
        "title": "API Verification Case",
        "description": "Testing full backend flow",
        "severity": 3,
        "tlp": 2,
        "pap": 2
    }
    r = requests.post(f"{BASE_URL}/cases", headers=HEADERS, json=payload)
    if not print_result("Create Case", r):
        return
    case_id = r.json().get("case_id")
    print(f"  -> Case ID: {case_id}")

    # 2. Flag Case (PATCH)
    payload = {"flag": True}
    r = requests.patch(f"{BASE_URL}/cases/{case_id}", headers=HEADERS, json=payload)
    print_result("Flag Case", r)

    # 2.5 Add Custom Field (PATCH)
    payload = {"customFields.business-impact": {"string": "High"}}
    r = requests.patch(f"{BASE_URL}/cases/{case_id}", headers=HEADERS, json=payload)
    print_result("Add Custom Field", r)

    # 2.6 Verify Custom Field Data (GET via Query Service)
    r = requests.get(f"{BASE_URL}/cases/{case_id}", headers=HEADERS)
    print_result("Verify Case Read", r)
    data = r.json()
    cfs = data.get("customFields", [])
    if len(cfs) > 0 and cfs[0].get("name") == "business-impact":
        print("  -> Custom Field serialization passed!")
    else:
        print("  -> [FAILED] Custom Field serialization failed or is empty.")
        print(f"  Data: {cfs}")

    # 3. Add Task
    payload = {"title": "API Verification Task"}
    r = requests.post(f"{BASE_URL}/case/{case_id}/task", headers=HEADERS, json=payload)
    print_result("Add Task", r)

    # 4. Add Observable
    payload = {
        "type": "domain",
        "value": "api-verification.com",
        "message": "Found via API test"
    }
    r = requests.post(f"{BASE_URL}/api/case/{case_id}/observable", headers=HEADERS, json=payload)
    print_result("Add Observable", r)

    # 5. Add Page
    payload = {
        "title": "API Verification Page",
        "content": "This is a test page content."
    }
    r = requests.post(f"{BASE_URL}/api/case/{case_id}/page", headers=HEADERS, json=payload)
    print_result("Add Page", r)

    # 6. Add TTP
    payload = {
        "tactic": "Initial Access",
        "techniqueId": "T1190",
        "techniqueName": "Exploit Public-Facing Application"
    }
    r = requests.post(f"{BASE_URL}/api/case/{case_id}/ttp", headers=HEADERS, json=payload)
    print_result("Add TTP", r)

    # 7. Close Case
    payload = {"status": "CLOSED", "resolutionStatus": "TruePositive"}
    r = requests.patch(f"{BASE_URL}/cases/{case_id}", headers=HEADERS, json=payload)
    print_result("Close Case", r)

    # 8. Export Case
    r = requests.get(f"{BASE_URL}/case/{case_id}/export", headers=HEADERS)
    print_result("Export Case", r)

    # 9. Duplicate / Merge Setup (Create a target case)
    payload = {"title": "Target Merge Case"}
    r_target = requests.post(f"{BASE_URL}/cases", headers=HEADERS, json=payload)
    target_case_id = r_target.json().get("case_id")
    
    # Merge Case
    payload = {"case_ids": [case_id]}
    r = requests.post(f"{BASE_URL}/cases/merge/{target_case_id},{case_id}", headers=HEADERS, json=payload)
    print_result("Merge Case", r)

    # 10. Delete Default Case
    r = requests.delete(f"{BASE_URL}/cases/{case_id}", headers=HEADERS)
    print_result("Delete Original Case", r)
    
    # 11. Delete Target Case
    r = requests.delete(f"{BASE_URL}/cases/{target_case_id}", headers=HEADERS)
    print_result("Delete Target Case", r)

    print("--- Verification Complete ---")

if __name__ == "__main__":
    # Give the containers a moment if they just restarted
    time.sleep(2)
    run_verification()
