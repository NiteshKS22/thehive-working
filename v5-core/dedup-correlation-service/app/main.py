import os
import json
import uuid
import time
import hashlib
import logging
import signal
import sys
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
import redis

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:29092")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
INPUT_TOPIC = "alerts.ingest.v1"
OUTPUT_TOPIC_ACCEPTED = "alerts.accepted.v1"
OUTPUT_TOPIC_DUPLICATE = "alerts.duplicate.v1"
DLQ_TOPIC = "alerts.ingest.dlq.v1"
DEDUP_WINDOW_SECONDS = int(os.getenv("DEDUP_WINDOW_SECONDS", 600))  # 10 minutes
AUTO_OFFSET_RESET = os.getenv("AUTO_OFFSET_RESET", "latest")

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("dedup-worker")

# State
running = True

def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def generate_fingerprint(payload, tenant_id):
    # Canonical fingerprint: hash(tenant_id + source + type + sourceRef)
    raw = f"{tenant_id}:{payload.get('source')}:{payload.get('type')}:{payload.get('sourceRef')}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def process_event(event, r, producer):
    payload = event.get('payload', {})
    trace_id = event.get('trace_id')
    event_id = event.get('event_id')

    # Extract tenant_id
    tenant_id = payload.get('tenant_id')

    if not tenant_id:
        # Send to DLQ
        logger.warning(f"Missing tenant_id for event {event_id}. Sending to DLQ.")
        dlq_event = event.copy()
        dlq_event['error'] = "Missing tenant_id"
        producer.send(DLQ_TOPIC, value=dlq_event)
        return

    fingerprint = generate_fingerprint(payload, tenant_id)
    redis_key = f"dedup:{tenant_id}:{fingerprint}"

    # Atomic check-and-set
    # set(..., nx=True) returns True (actually ok string or something depending on lib version, usually True/None)
    # redis-py: set(nx=True) returns True if set, None if not set.
    is_new = r.set(redis_key, event_id, ex=DEDUP_WINDOW_SECONDS, nx=True)
    is_duplicate = not is_new

    output_event = {
        "event_id": str(uuid.uuid4()),
        "trace_id": trace_id,
        "tenant_id": tenant_id,
        "timestamp": int(time.time() * 1000),
        "schema_version": "1.0",
        "payload": {
            "original_event_id": event_id,
            "fingerprint": fingerprint,
            "original_payload": payload
        }
    }

    if is_duplicate:
        # It's a duplicate
        count = r.incr(f"count:{tenant_id}:{fingerprint}")
        r.expire(f"count:{tenant_id}:{fingerprint}", DEDUP_WINDOW_SECONDS)

        output_event["type"] = "AlertDuplicateRejected"
        output_event["payload"]["count"] = count
        output_event["payload"]["decision"] = "rejected"

        producer.send(OUTPUT_TOPIC_DUPLICATE, value=output_event)
        logger.info(f"Duplicate rejected: {fingerprint} tenant={tenant_id}")
    else:
        # It's new (accepted)
        r.set(f"count:{tenant_id}:{fingerprint}", 1, ex=DEDUP_WINDOW_SECONDS)

        output_event["type"] = "AlertAccepted"
        output_event["payload"]["decision"] = "accepted"

        producer.send(OUTPUT_TOPIC_ACCEPTED, value=output_event)
        logger.info(f"Alert accepted: {fingerprint} tenant={tenant_id}")


def main():
    logger.info("Starting Dedup Worker (Phase 3B)")

    # Initialize Redis
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
        logger.info("Connected to Redis")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        sys.exit(1)

    # Initialize Kafka
    try:
        consumer = KafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id="dedup-group-v1",
            auto_offset_reset=AUTO_OFFSET_RESET,
            enable_auto_commit=False, # Manual commit for safety
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        logger.info(f"Connected to Kafka/Redpanda (Offset: {AUTO_OFFSET_RESET})")
    except Exception as e:
        logger.error(f"Kafka connection failed: {e}")
        sys.exit(1)

    while running:
        try:
            # Poll for messages
            msg_pack = consumer.poll(timeout_ms=1000)

            for tp, messages in msg_pack.items():
                for message in messages:
                    process_event(message.value, r, producer)

            # Critical: Flush producer then commit offsets
            if msg_pack:
                producer.flush()
                consumer.commit()

        except Exception as e:
            logger.error(f"Error in processing loop: {e}")
            time.sleep(1)

    logger.info("Worker stopped")
    producer.close()
    consumer.close()

if __name__ == "__main__":
    main()
