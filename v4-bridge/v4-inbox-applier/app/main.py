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

    # B1-BLOCK-01: Disable auto-commit for reliability
    consumer = KafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="v4-inbox-group",
        enable_auto_commit=False,
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )

    logger.info("Starting Inbox Applier")

    while running:
        # 1. Consume & Buffer to DB
        msg_pack = consumer.poll(timeout_ms=500)
        commit_needed = False

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
                    commit_needed = True
                except Exception as e:
                    logger.error(f"Insert failed: {e}")
                    # B1-BLOCK-01: Do NOT commit if insert fails.
                    # Backoff and retry (loop continues next iteration)
                    # For strict ordering, we should probably break inner loop and not commit?
                    # Yes, break to retry this batch or message?
                    # Poll returns batch. If msg 1 ok, msg 2 fail. We cannot commit msg 2.
                    # Ideally we break and rely on Kafka to re-deliver uncommitted offsets?
                    # Or we explicitly do not set commit_needed=True for this batch if any fail?
                    # BUT if we processed msg 1, we want to commit it?
                    # Kafka manual commit commits *all* up to offset.
                    # So if msg 2 fails, we cannot commit msg 2. We could commit msg 1 manually.
                    # Simplified: If any error in batch, do not commit ANY of the batch.
                    # Rely on idempotency of insert_inbox_row (ON CONFLICT DO NOTHING) for replays.
                    commit_needed = False
                    time.sleep(2) # Backoff
                    break

            if not commit_needed:
                break # Break outer tp loop too

        if commit_needed:
            try:
                consumer.commit()
            except Exception as e:
                logger.error(f"Commit failed: {e}")

        # 2. Claim & Apply (Decoupled from Kafka loop, runs against DB state)
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
