import os
import time
import json
import logging
import signal
import uuid
from kafka import KafkaConsumer
from app.db import insert_inbox_row, claim_pending_rows, mark_applied, mark_conflict
from app.apply import apply_change
from app.metrics_server import start_metrics_server, INBOX_ROWS_WRITTEN, APPLY_SUCCESS, APPLY_CONFLICT

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("v4-inbox-applier")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:29092")
INPUT_TOPIC = "bridge.v5.case.writeback.v1"
ENABLED = os.getenv("V5_WRITEBACK_ENABLED", "false").lower() == "true"

running = True

def signal_handler(sig, frame):
    global running
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    start_metrics_server()

    if not ENABLED:
        logger.info("Writeback Applier disabled.")
        while running:
            time.sleep(10)
        return

    consumer = KafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="v4-inbox-group",
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )

    logger.info("Starting Inbox Applier")

    while running:
        # 1. Consume & Buffer to DB
        msg_pack = consumer.poll(timeout_ms=500)
        for tp, messages in msg_pack.items():
            for msg in messages:
                try:
                    event = msg.value
                    row = {
                        "id": str(uuid.uuid4()),
                        "tenant_id": event['tenant_id'],
                        "entity_type": "CASE", # Simplification
                        "entity_id": event['payload']['case_id'],
                        "source_event_id": event['event_id'],
                        "origin": event['meta']['origin'],
                        "payload_json": json.dumps(event['payload']),
                        "created_at": int(time.time() * 1000)
                    }
                    insert_inbox_row(row)
                    INBOX_ROWS_WRITTEN.labels(status="success").inc()
                except Exception as e:
                    logger.error(f"Insert failed: {e}")

        # 2. Claim & Apply
        try:
            rows = claim_pending_rows(limit=10)
            for row in rows:
                if apply_change(row):
                    mark_applied(row['id'])
                    APPLY_SUCCESS.labels(type="case").inc()
                else:
                    mark_conflict(row['id'], "Conflict detected")
                    APPLY_CONFLICT.labels(type="case").inc()
        except Exception as e:
            logger.error(f"Apply loop failed: {e}")
            time.sleep(1)

    consumer.close()

if __name__ == "__main__":
    main()
