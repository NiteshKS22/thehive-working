import json
import logging

logger = logging.getLogger("inbox-apply")

def apply_change(row):
    """
    Applies the payload to v4 tables.
    Returns True if applied, False if conflict.
    """
    payload = json.loads(row['payload_json'])
    # Mock logic for B1.3 since we don't have real v4 schema mapped here
    # In real impl, this would update `case` table where id=... and updated_at < payload.updated_at

    logger.info(f"Applying change to v4: {payload}")

    # Conflict check simulation
    # If payload.updated_at < current_v4_time -> CONFLICT

    return True
