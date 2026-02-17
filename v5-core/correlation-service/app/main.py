import os
import json
import logging
import signal
import sys
import time
import uuid
import threading
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
OUTPUT_TOPIC_AUDIT = "correlation.audit.v1" # New audit topic
DLQ_TOPIC = "correlation.dlq.v1"
RULES_FILE = os.getenv("RULES_FILE", "rules.yaml")
RULE_REFRESH_INTERVAL = int(os.getenv("RULE_REFRESH_INTERVAL", 60)) # Seconds

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("correlation-worker")

running = True

def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def rule_reloader(engine):
    while running:
        time.sleep(RULE_REFRESH_INTERVAL)
        try:
            engine.reload_rules()
        except Exception as e:
            logger.error(f"Rule reload failed: {e}")

def main():
    logger.info("Starting Correlation Worker (Phase 3D/3F)")

    # Initialize components
    try:
        db = Database()
        rules_engine = RuleEngine(db_instance=db) # Load from DB

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

    # Start reloader thread
    reloader = threading.Thread(target=rule_reloader, args=(rules_engine,), daemon=True)
    reloader.start()

    while running:
        try:
            msg_pack = consumer.poll(timeout_ms=1000)

            for tp, messages in msg_pack.items():
                batch_success = True
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
                            logger.error(f"Missing required fields: {event}. Sending to DLQ.")
                            # FIX C1: Must succeed DLQ or fail batch
                            try:
                                dlq_event = {
                                    "event_id": str(uuid.uuid4()),
                                    "type": "CorrelationDLQ",
                                    "tenant_id": tenant_id or "unknown",
                                    "trace_id": trace_id,
                                    "timestamp": int(time.time() * 1000),
                                    "schema_version": "1.0",
                                    "payload": {
                                        "reason": "Missing tenant_id or original_event_id",
                                        "original_message": event
                                    }
                                }
                                producer.send(DLQ_TOPIC, dlq_event)
                            except Exception as dlq_e:
                                logger.error(f"DLQ failed: {dlq_e}")
                                batch_success = False
                                break # Stop batch processing
                            continue

                        # Evaluate Rules
                        matches = rules_engine.evaluate(tenant_id, original_payload, timestamp)

                        for match in matches:
                            group_id = match['group_id']

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
                            }

                            link_data = {
                                "tenant_id": tenant_id,
                                "group_id": group_id,
                                "original_event_id": original_event_id,
                                "linked_at": int(time.time() * 1000),
                                "link_reason": f"Rule: {match['rule_name']}"
                            }

                            # Process in DB
                            # FIX C1: If DB fails, exception raises, caught below -> batch fails
                            is_new_group, is_new_link, new_count, new_severity = db.process_correlation(group_data, link_data)

                            key_bytes = group_id.encode('utf-8')

                            if is_new_group:
                                group_event_payload = group_data.copy()
                                group_event_payload['alert_count'] = new_count
                                group_event_payload['max_severity'] = new_severity

                                producer.send(OUTPUT_TOPIC_GROUP_CREATED, key=key_bytes, value={
                                    "event_id": str(uuid.uuid4()),
                                    "type": "CorrelationGroupCreated",
                                    "trace_id": trace_id,
                                    "tenant_id": tenant_id,
                                    "timestamp": int(time.time() * 1000),
                                    "schema_version": "1.0",
                                    "payload": group_event_payload
                                })
                                logger.info(f"Group Created: {group_id}")

                            if is_new_link and not is_new_group:
                                producer.send(OUTPUT_TOPIC_GROUP_UPDATED, key=key_bytes, value={
                                    "event_id": str(uuid.uuid4()),
                                    "type": "CorrelationGroupUpdated",
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
                                        "rule_name": match['rule_name']
                                    }
                                })
                                logger.info(f"Group Updated: {group_id} (count={new_count})")

                            if is_new_link:
                                producer.send(OUTPUT_TOPIC_ALERT_LINKED, key=key_bytes, value={
                                    "event_id": str(uuid.uuid4()),
                                    "type": "AlertLinkedToGroup",
                                    "trace_id": trace_id,
                                    "tenant_id": tenant_id,
                                    "timestamp": int(time.time() * 1000),
                                    "schema_version": "1.0",
                                    "payload": link_data
                                })

                                producer.send(OUTPUT_TOPIC_AUDIT, key=key_bytes, value={
                                    "event_id": str(uuid.uuid4()),
                                    "type": "CorrelationDecision",
                                    "trace_id": trace_id,
                                    "tenant_id": tenant_id,
                                    "timestamp": int(time.time() * 1000),
                                    "schema_version": "1.0",
                                    "payload": {
                                        "decision": "linked",
                                        "rule_id": match['rule_id'],
                                        "group_id": group_id,
                                        "alert_id": original_event_id,
                                        "correlation_key": match['correlation_key']
                                    }
                                })

                    except Exception as e:
                        # Catch processing error (DB, logic)
                        logger.error(f"Error processing message: {e}")
                        # Try DLQ
                        try:
                            producer.send(DLQ_TOPIC, {
                                "event_id": str(uuid.uuid4()),
                                "type": "CorrelationDLQ",
                                "tenant_id": "unknown",
                                "timestamp": int(time.time() * 1000),
                                "payload": {"reason": f"Processing error: {str(e)}", "original_message": str(message.value)}
                            })
                        except:
                            # If DLQ fails, we must fail batch
                            logger.error("DLQ failed after processing error. Failing batch.")
                            batch_success = False
                            break
                        continue # Continue to next message if DLQ OK

                # Commit offsets ONLY if batch success
                if batch_success:
                    producer.flush()
                    consumer.commit()
                else:
                    # If batch failed, we don't commit. Next poll/restart will replay.
                    # We might process some dupes, but operations are idempotent.
                    logger.warning("Batch failed. Not committing offsets.")

        except Exception as e:
            logger.error(f"Error in consumer loop: {e}")
            time.sleep(1)

    logger.info("Worker stopped")
    producer.close()
    consumer.close()
    db.close()

if __name__ == "__main__":
    main()
