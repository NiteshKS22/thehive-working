import time
import logging
import signal
import sys
from app.db import claim_outbox_rows, mark_published, mark_failed
from app.publisher import get_producer, publish_event
from app.metrics_server import start_metrics_server, OUTBOX_CLAIMED, OUTBOX_PUBLISHED, OUTBOX_FAILED

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("v4-publisher")

running = True

def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    logger.info("Starting v4 Outbox Publisher (Phase B1.1)")
    start_metrics_server()

    try:
        producer = get_producer()
    except Exception as e:
        logger.error(f"Failed to init Kafka: {e}")
        sys.exit(1)

    while running:
        try:
            # Polling
            rows = claim_outbox_rows(limit=100)
            if not rows:
                time.sleep(0.5)
                continue

            OUTBOX_CLAIMED.labels(service="v4-publisher").inc(len(rows))
            logger.info(f"Claimed {len(rows)} events")

            futures = {}
            for row in rows:
                try:
                    future = publish_event(producer, row)
                    futures[row['outbox_id']] = (future, row['event_type'])
                except Exception as e:
                    logger.error(f"Publish error {row['outbox_id']}: {e}")
                    mark_failed(row['outbox_id'], str(e))
                    OUTBOX_FAILED.labels(service="v4-publisher").inc()

            # Flush batch
            producer.flush()

            # Mark Success (only if future ok)
            for oid, (future, event_type) in futures.items():
                try:
                    future.get(timeout=5)
                    mark_published(oid)
                    topic = f"bridge.v4.{event_type}"
                    OUTBOX_PUBLISHED.labels(service="v4-publisher", topic=topic).inc()
                except Exception as e:
                    logger.error(f"Flush error {oid}: {e}")
                    mark_failed(oid, str(e))
                    OUTBOX_FAILED.labels(service="v4-publisher").inc()

        except Exception as e:
            logger.error(f"Loop error: {e}")
            time.sleep(1)

    producer.close()

if __name__ == "__main__":
    main()
