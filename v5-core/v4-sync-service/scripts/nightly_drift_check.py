import os
import logging
import hashlib
import json
import time
from opensearchpy import OpenSearch
from app.metrics_server import DRIFT_DETECTED

# Simulating v4 connection for this B1 implementation
# In real life, this would connect to v4 Postgres/Cassandra
def get_v4_state(case_id):
    # Mock data for demonstration - in real impl, this fetches from v4 DB
    # We simulate a "canonical" dictionary that should match v5
    return {
        "case_id": case_id,
        "title": f"Incident {case_id}",
        "status": "Open",
        "severity": 3,
        "updated_at": int(time.time() * 1000)
    }

def compute_state_hash(state):
    """
    Computes a stable hash of the canonical fields.
    Fields: case_id, title, status, severity, updated_at (or content fields if timestamps unreliable).
    """
    canonical_keys = ["case_id", "title", "status", "severity", "updated_at"]
    canonical_data = {k: state.get(k) for k in canonical_keys}
    # Sort keys to ensure stable JSON
    serialized = json.dumps(canonical_data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

def check_drift():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("drift-check")

    opensearch_host = os.getenv("OPENSEARCH_HOST", "opensearch")
    opensearch_port = int(os.getenv("OPENSEARCH_PORT", 9200))
    use_ssl = os.getenv("OPENSEARCH_USE_SSL", "false").lower() == "true"
    verify_certs = os.getenv("OPENSEARCH_VERIFY_CERTS", "true").lower() == "true"

    logger.info(f"Starting Nightly Drift Check (Hash-Based). SSL={use_ssl}")

    # Connect to v5
    os_client = OpenSearch(
        hosts=[{'host': opensearch_host, 'port': opensearch_port}],
        use_ssl=use_ssl,
        verify_certs=verify_certs if use_ssl else False
    )

    try:
        # Scan recent cases
        query = {"query": {"match_all": {}}}
        resp = os_client.search(index="cases-v1", body=query, size=100)

        for hit in resp['hits']['hits']:
            v5_case = hit['_source']
            case_id = v5_case.get('case_id')

            # Fetch v4 authoritative state
            v4_case = get_v4_state(case_id)

            # Hash Comparison
            v5_hash = compute_state_hash(v5_case)
            v4_hash = compute_state_hash(v4_case)

            if v5_hash != v4_hash:
                logger.warning(f"Drift Detected for {case_id}. v5_hash={v5_hash} v4_hash={v4_hash}")
                # In real job, push metric to PushGateway
                # DRIFT_DETECTED.labels(resource_type="case").inc()
            else:
                logger.debug(f"Case {case_id} is in sync.")

    except Exception as e:
        logger.error(f"Drift check failed: {e}")

if __name__ == "__main__":
    check_drift()
