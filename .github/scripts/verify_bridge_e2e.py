import os
import sys
import time
import requests
from opensearchpy import OpenSearch

# Configuration
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", 9200))
QUERY_API_URL = os.getenv("QUERY_API_URL", "http://localhost:8001")

def get_opensearch_client():
    return OpenSearch(
        hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
        http_compress=True,
        use_ssl=False
    )

def verify():
    print("Verifying Bridge E2E...")
    client = get_opensearch_client()

    # Retry loop
    max_retries = 20
    for i in range(max_retries):
        print(f"Attempt {i+1}/{max_retries}...")
        try:
            # 1. Verify Case A (Tenant A) exists
            # We check raw OpenSearch to ensure index population, but we must check tenant_id field
            res_a = client.get(index="cases-v1", id="tenant-A:case-A-100")
            source_a = res_a['_source']
            if source_a['title'] != "Bridge Case A":
                raise Exception("Title mismatch Case A")
            if source_a['tenant_id'] != "tenant-A":
                raise Exception("Tenant Leakage Case A")

            # 2. Verify Alert A (Tenant A)
            res_alert = client.get(index="alerts-v1", id="tenant-A:alert-A-200")
            if res_alert['_source']['title'] != "Bridge Alert A":
                raise Exception("Title mismatch Alert A")

            # 3. Verify Tenant B Case
            res_b = client.get(index="cases-v1", id="tenant-B:case-B-300")
            if res_b['_source']['tenant_id'] != "tenant-B":
                raise Exception("Tenant Leakage Case B")

            print("SUCCESS: All docs found in OpenSearch.")
            return

        except Exception as e:
            print(f"Check failed: {e}")
            time.sleep(2)

    print("FAILURE: Timed out waiting for bridge sync.")
    sys.exit(1)

if __name__ == "__main__":
    verify()
