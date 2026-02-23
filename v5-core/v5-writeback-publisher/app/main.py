import os
import json
import logging
import signal
import sys
from kafka import KafkaConsumer, KafkaProducer
from app.mapper import map_case_event
from app.metrics_server import start_metrics_server, EVENTS_PROCESSED, EVENTS_PUBLISHED

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("v5-writeback")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:29092")
INPUT_TOPIC = "cases.updated.v1" # Listening to v5 events
OUTPUT_TOPIC = "bridge.v5.case.writeback.v1"
ENABLED = os.getenv("V5_WRITEBACK_ENABLED", "false").lower() == "true"

running = True

def signal_handler(sig, frame):
    global running
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    if not ENABLED:
        logger.info("Writeback disabled via flag.")
        while running:
            time.sleep(10)
        return

    start_metrics_server()

    consumer = KafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="v5-writeback-group",
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda m: json.dumps(m).encode('utf-8')
    )

    logger.info("Starting Writeback Publisher")

    while running:
        msg_pack = consumer.poll(timeout_ms=1000)
        for tp, messages in msg_pack.items():
            for message in messages:
                try:
                    event = message.value

                    # Loop Prevention
                    if event.get('meta', {}).get('origin') == 'v4':
                        logger.debug("Skipping v4-origin event")
                        continue

                    # Map
                    mapped_payload = map_case_event(event)

                    # Envelope
                    out_event = {
                        "event_id": str(uuid.uuid4()),
                        "type": "V5CaseWritebackRequested",
                        "tenant_id": event.get('tenant_id'),
                        "meta": {
                            "origin": "v5",
                            "bridge_id": "v5-writeback-1"
                        },
                        "payload": mapped_payload,
                        "timestamp": int(time.time() * 1000)
                    }

                    key = f"{event.get('tenant_id')}:{mapped_payload.get('case_id')}"
                    producer.send(OUTPUT_TOPIC, key=key.encode('utf-8'), value=out_event)
                    EVENTS_PUBLISHED.labels(topic=OUTPUT_TOPIC).inc()

                except Exception as e:
                    logger.error(f"Error: {e}")
                    EVENTS_PROCESSED.labels(status="error").inc()

    consumer.close()
    producer.close()

if __name__ == "__main__":
    import time
    import uuid
    main()
