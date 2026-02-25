import os
import json
import logging
import requests
import time
from kafka import KafkaConsumer

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("reverse-bridge")

KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:29092")
V4_API_URL = os.getenv("V4_API_URL", "http://thehive:9000/api")
V4_API_KEY = os.getenv("V4_API_KEY", "simulated-key")

def get_headers():
    return {
        "Authorization": f"Bearer {V4_API_KEY}",
        "Content-Type": "application/json"
    }

def handle_case_created(payload):
    case_id = payload.get("case_id")
    title = payload.get("title")
    desc = payload.get("description")
    severity = payload.get("severity", 2)
    tlp = payload.get("tlp", 2)
    pap = payload.get("pap", 2)
    owner = payload.get("assigned_to", "")

    # Map to v4 Case
    # Note: 'v5_ref' custom field must exist in v4. If not, this might fail or be ignored.
    # We assume it exists or is created by migration script.
    data = {
        "title": title,
        "description": desc,
        "severity": severity,
        "tlp": tlp,
        "pap": pap,
        "owner": owner,
        "flag": False,
        "customFields": {
            "v5_ref": {"string": case_id, "order": 0}
        }
    }

    logger.info(f"Mirroring CaseCreated to v4: {title} (v5: {case_id})")
    try:
        # Check if exists first? Or just try create
        resp = requests.post(f"{V4_API_URL}/case", json=data, headers=get_headers(), timeout=5)

        if resp.status_code == 201:
            v4_id = resp.json().get("id")
            logger.info(f"Successfully mirrored to v4. Legacy ID: {v4_id}")
        elif resp.status_code == 409:
            logger.warning(f"Conflict: Case '{title}' already exists in v4. Skipping creation.")
        else:
            logger.error(f"Failed to mirror case: {resp.status_code} {resp.text}")

    except Exception as e:
        logger.error(f"Error calling v4 API: {e}")

def main():
    logger.info("Reverse Bridge starting...")
    while True:
        try:
            consumer = KafkaConsumer(
                "nv.cases.created.v1",
                # "nv.cases.updated.v1", # TODO: Implement updates
                bootstrap_servers=KAFKA_SERVERS,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id="reverse-bridge-group",
                auto_offset_reset='latest'
            )
            logger.info("Kafka Consumer connected.")
            break
        except Exception as e:
            logger.warning(f"Kafka connection failed, retrying: {e}")
            time.sleep(5)

    for msg in consumer:
        try:
            event = msg.value
            event_type = event.get("type")
            payload = event.get("payload", {})

            if event_type == "CaseCreated":
                handle_case_created(payload)

        except Exception as e:
            logger.error(f"Error processing message: {e}")

if __name__ == "__main__":
    main()
