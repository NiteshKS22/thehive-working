import logging
import time
from app.metrics_server import DRIFT_DETECTED

logger = logging.getLogger("drift-detector")

def detect_drift(v4_state, v5_state):
    """
    Compares v4 and v5 state hashes.
    If different, logs drift.
    """
    v4_hash = hash(str(v4_state))
    v5_hash = hash(str(v5_state))

    if v4_hash != v5_hash:
        logger.warning(f"Drift Detected! v4={v4_hash}, v5={v5_hash}")
        DRIFT_DETECTED.labels(resource_type="case").inc()
        return True
    return False
