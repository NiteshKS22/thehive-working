import os
import json
import logging
import signal
import sys
import time
import uuid
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from rules import RuleEngine
from db import Database

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:29092")
INPUT_TOPIC = "alerts.accepted.v1"
OUTPUT_TOPIC_GROUP_CREATED = "correlation.group.created.v1"
OUTPUT_TOPIC_GROUP_UPDATED = "correlation.group.updated.v1"
OUTPUT_TOPIC_ALERT_LINKED = "correlation.alert.linked.v1"
DLQ_TOPIC = "correlation.dlq.v1"
RULES_FILE = os.getenv("RULES_FILE", "rules.yaml")

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("correlation-worker")

running = True

def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    logger.info("Starting Correlation Worker (Phase 3D)")

    # Initialize components
    try:
        rules_engine = RuleEngine(RULES_FILE)
        db = Database()

        consumer = KafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id="correlation-group-v1",
            auto_offset_reset='latest',
            enable_auto_commit=False,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        logger.info("Connected to Kafka/Postgres")
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        sys.exit(1)

    while running:
        try:
            msg_pack = consumer.poll(timeout_ms=1000)

            for tp, messages in msg_pack.items():
                for message in messages:
                    try:
                        event = message.value
                        payload = event.get('payload', {})

                        original_event_id = payload.get('original_event_id')
                        original_payload = payload.get('original_payload', {})
                        tenant_id = event.get('tenant_id')
                        timestamp = event.get('timestamp')
                        trace_id = event.get('trace_id')

                        if not tenant_id or not original_event_id:
                            logger.error(f"Missing required fields: {event}")
                            continue

                        # Evaluate Rules
                        matches = rules_engine.evaluate(tenant_id, original_payload, timestamp)

                        for match in matches:
                            group_id = match['group_id']

                            # Prepare Data
                            group_data = {
                                "tenant_id": tenant_id,
                                "group_id": group_id,
                                "correlation_key": match['correlation_key'],
                                "rule_id": match['rule_id'],
                                "rule_name": match['rule_name'],
                                "confidence": match['confidence'],
                                "status": "OPEN",
                                "first_seen": timestamp,
                                "last_seen": timestamp,
                                "max_severity": match['max_severity'],
                                # alert_count handled in DB logic
                            }

                            link_data = {
                                "tenant_id": tenant_id,
                                "group_id": group_id,
                                "original_event_id": original_event_id,
                                "linked_at": int(time.time() * 1000),
                                "link_reason": f"Rule: {match['rule_name']}"
                            }

                            # Process in DB
                            is_new_group, is_new_link, new_count, new_severity = db.process_correlation(group_data, link_data)

                            if is_new_group:
                                # Emit Group Created
                                # Payload should contain complete group info
                                group_event_payload = group_data.copy()
                                group_event_payload['alert_count'] = new_count # Should be 1
                                group_event_payload['max_severity'] = new_severity

                                producer.send(OUTPUT_TOPIC_GROUP_CREATED, {
                                    "event_id": str(uuid.uuid4()),
                                    "trace_id": trace_id,
                                    "tenant_id": tenant_id,
                                    "timestamp": int(time.time() * 1000),
                                    "schema_version": "1.0",
                                    "payload": group_event_payload
                                })
                                logger.info(f"Group Created: {group_id}")

                            if is_new_link and not is_new_group:
                                # Emit Group Updated with new stats
                                producer.send(OUTPUT_TOPIC_GROUP_UPDATED, {
                                    "event_id": str(uuid.uuid4()),
                                    "trace_id": trace_id,
                                    "tenant_id": tenant_id,
                                    "timestamp": int(time.time() * 1000),
                                    "schema_version": "1.0",
                                    "payload": {
                                        "group_id": group_id,
                                        "status": "OPEN",
                                        "last_seen": timestamp,
                                        "alert_count": new_count,
                                        "max_severity": new_severity,
                                        "rule_name": match['rule_name'] # Useful for indexing if needed
                                    }
                                })
                                logger.info(f"Group Updated: {group_id} (count={new_count})")

                            if is_new_link:
                                # Emit Alert Linked
                                producer.send(OUTPUT_TOPIC_ALERT_LINKED, {
                                    "event_id": str(uuid.uuid4()),
                                    "trace_id": trace_id,
                                    "tenant_id": tenant_id,
                                    "timestamp": int(time.time() * 1000),
                                    "schema_version": "1.0",
                                    "payload": link_data
                                })

                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        continue

            # Commit offsets
            if msg_pack:
                producer.flush()
                consumer.commit()

        except Exception as e:
            logger.error(f"Error in consumer loop: {e}")
            time.sleep(1)

    logger.info("Worker stopped")
    producer.close()
    consumer.close()
    db.close()

if __name__ == "__main__":
    main()
