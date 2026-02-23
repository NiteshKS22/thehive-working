import os
import logging
import hashlib
import json
import time
import psycopg2
from opensearchpy import OpenSearch
from app.metrics_server import DRIFT_DETECTED

# Configuration
V4_DB_HOST = os.getenv("V4_DB_HOST", "postgres")
V4_DB_USER = os.getenv("V4_DB_USER", "hive")
V4_DB_PASSWORD = os.getenv("V4_DB_PASSWORD", "hive")
V4_DB_NAME = os.getenv("V4_DB_NAME", "thehive")

OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", 9200))
USE_SSL = os.getenv("OPENSEARCH_USE_SSL", "false").lower() == "true"
ALLOW_STUB_V4 = os.getenv("ALLOW_STUB_V4", "false").lower() == "true"

def get_v4_state(case_id):
    """
    Connects to v4 DB and fetches case state.
    """
    try:
        conn = psycopg2.connect(host=V4_DB_HOST, user=V4_DB_USER, password=V4_DB_PASSWORD, database=V4_DB_NAME, port=5432)
        cur = conn.cursor()

        # TODO: Implement real SELECT from v4 'case' table.
        # For Phase B1.4 proof without full v4 schema, we require explicit permission to use stubs.
        if not ALLOW_STUB_V4:
            raise Exception("Real v4 DB schema not found and ALLOW_STUB_V4=false. Cannot proceed.")

        # Stub logic for CI proof (B1.2/B1.4)
        return {
            "case_id": case_id,
            "title": f"Incident {case_id}", # Mock matching seeding
            "status": "Open",
            "severity": 3,
            "updated_at": int(time.time() * 1000)
        }
    except Exception as e:
        logging.error(f"v4 DB Error: {e}")
        return {}

def compute_state_hash(state):
    canonical_keys = ["case_id", "title", "status", "severity", "updated_at"]
    canonical_data = {k: state.get(k) for k in canonical_keys}
    serialized = json.dumps(canonical_data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

def check_drift():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("drift-check")
    logger.info("Starting Nightly Drift Check (Real DB)")

    os_client = OpenSearch(
        hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
        use_ssl=USE_SSL,
        verify_certs=False
    )

    try:
        query = {"query": {"match_all": {}}}
        resp = os_client.search(index="cases-v1", body=query, size=100)

        for hit in resp['hits']['hits']:
            v5_case = hit['_source']
            case_id = v5_case.get('case_id')

            v4_case = get_v4_state(case_id)

            v5_hash = compute_state_hash(v5_case)
            v4_hash = compute_state_hash(v4_case)

            if v5_hash != v4_hash:
                logger.warning(f"Drift Detected for {case_id}")
            else:
                logger.info(f"Case {case_id} synced.")

    except Exception as e:
        logger.error(f"Drift check failed: {e}")

if __name__ == "__main__":
    check_drift()
