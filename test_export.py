import os
import requests
import pyzipper
import json

BASE_URL = "http://nv-case-engine:8000/cases"
TENANT = "dev-tenant"
AUTH = ("dev-user@neuralvyuha.com", "devuser123")
PASSWORD = "supersecretpassword123"

def main():
    import psycopg2
    print("[*] Fetching cases from DB...")
    conn = psycopg2.connect("host=nv-postgres dbname=nv_vault user=nv_user password=nv_pass")
    with conn.cursor() as cur:
        cur.execute("SELECT case_id, tenant_id FROM cases WHERE tenant_id = 'dev-tenant' LIMIT 1")
        row = cur.fetchone()
        if not row:
            print("[-] No cases found.")
            return
        case_id = row[0]
        actual_tenant = row[1]
    conn.close()
    print(f"[*] Selected Case ID: {case_id} (Tenant: {actual_tenant})")

    print("[*] Testing Plain JSON Export...")
    res = requests.get(f"{BASE_URL}/{case_id}/export", auth=AUTH)
    assert res.status_code == 200, f"Failed plain export: {res.status_code} - {res.text}"
    data = res.json()
    print(f"[+] Exported JSON version {data.get('version')}")

    print(f"[*] Testing Secure ZIP Export with password '{PASSWORD}'...")
    res = requests.get(f"{BASE_URL}/{case_id}/export", params={"password": PASSWORD}, auth=AUTH)
    assert res.status_code == 200, f"Failed secure export: {res.status_code} - {res.text}"
    
    zip_path = "/tmp/test_case.zip"
    with open(zip_path, "wb") as f:
        f.write(res.content)
    
    print("[*] Verifying ZIP properties...")
    extracted_json = None
    try:
        with pyzipper.AESZipFile(zip_path, 'r') as zf:
            zf.setpassword(PASSWORD.encode('utf-8'))
            names = zf.namelist()
            print(f"[+] Files in zip: {names}")
            assert len(names) == 1
            with zf.open(names[0]) as f:
                extracted_json = json.loads(f.read().decode('utf-8'))
    except pyzipper.zipfile.BadZipFile:
        print(f"[-] Bad zip file. First 200 bytes of response:\n{res.content[:200]}")
        return
    
    print("[+] Extracted JSON successfully from encrypted ZIP.")
    assert extracted_json["case"]["id"] == case_id, "Mismatch Case ID"

    print("[*] Testing Import Functionality...")
    extracted_json["case"]["title"] += " (Imported Edition)"
    
    res = requests.post(f"{BASE_URL}/import", json=extracted_json, auth=AUTH)
    if res.status_code != 201:
        print(f"[-] Import failed: {res.text}")
        return
        
    new_case_id = res.json()["case_id"]
    print(f"[+] Successfully Imported to new Case ID: {new_case_id}")

if __name__ == "__main__":
    main()
