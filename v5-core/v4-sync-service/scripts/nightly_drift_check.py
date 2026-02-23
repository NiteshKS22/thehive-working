import os
import sys
import logging
import hashlib
import json
import time
import psycopg2
from opensearchpy import OpenSearch

# Path setup for secrets loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../common')))
try:
    from config.secrets import get_secret
except ImportError:
    # Fallback for local run without full common tree in path
    def get_secret(key, default=None):
        return os.getenv(key, default)

# Configuration
V4_DB_HOST = get_secret("V4_DB_HOST", "postgres")
V4_DB_USER = get_secret("V4_DB_USER", "hive")
V4_DB_PASSWORD = get_secret("V4_DB_PASSWORD", "hive")
V4_DB_NAME = get_secret("V4_DB_NAME", "thehive")

OPENSEARCH_HOST = get_secret("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT = int(get_secret("OPENSEARCH_PORT", 9200))
USE_SSL = get_secret("OPENSEARCH_USE_SSL", "false").lower() == "true"
# B1-BLOCK-02: Support verify certs logic
VERIFY_CERTS = get_secret("OPENSEARCH_VERIFY_CERTS", "true").lower() == "true"
CA_CERTS = get_secret("OPENSEARCH_CA_CERTS", None)

ALLOW_STUB_V4 = get_secret("ALLOW_STUB_V4", "false").lower() == "true"

def get_v4_state(case_id):
    """
    Connects to v4 DB and fetches case state.
    """
    try:
        conn = psycopg2.connect(host=V4_DB_HOST, user=V4_DB_USER, password=V4_DB_PASSWORD, database=V4_DB_NAME, port=5432)
        cur = conn.cursor()

        # TODO: Implement real SELECT from v4 'case' table.
        if not ALLOW_STUB_V4:
            raise Exception("Real v4 DB schema not found and ALLOW_STUB_V4=false. Cannot proceed.")

        return {
            "case_id": case_id,
            "title": f"Incident {case_id}",
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
    logger.info(f"Starting Nightly Drift Check. SSL={USE_SSL}, Verify={VERIFY_CERTS}")

    # B1-BLOCK-02: Pass verify_certs and ca_certs
    os_client = OpenSearch(
        hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
        use_ssl=USE_SSL,
        verify_certs=VERIFY_CERTS if USE_SSL else False,
        ca_certs=CA_CERTS if (USE_SSL and CA_CERTS) else None
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
