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
DEDUP_WINDOW_SECONDS = int(os.getenv("DEDUP_WINDOW_SECONDS", 600))  # 10 minutes

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

def generate_fingerprint(payload):
    # Canonical fingerprint: hash(source + type + sourceRef)
    # Tenant ID would be added here in multi-tenant setup
    raw = f"{payload.get('source')}:{payload.get('type')}:{payload.get('sourceRef')}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def main():
    logger.info("Starting Dedup & Correlation Worker")

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
            auto_offset_reset='earliest',
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        logger.info("Connected to Kafka/Redpanda")
    except Exception as e:
        logger.error(f"Kafka connection failed: {e}")
        sys.exit(1)

    while running:
        try:
            # Poll for messages (short timeout to allow checking 'running' flag)
            msg_pack = consumer.poll(timeout_ms=1000)

            for tp, messages in msg_pack.items():
                for message in messages:
                    event = message.value
                    payload = event.get('payload', {})
                    trace_id = event.get('trace_id')
                    event_id = event.get('event_id')

                    fingerprint = generate_fingerprint(payload)
                    redis_key = f"dedup:{fingerprint}"

                    # Atomic check-and-set
                    # If key exists, it's a duplicate within the window
                    # If not, set it with TTL
                    is_duplicate = r.set(redis_key, event_id, ex=DEDUP_WINDOW_SECONDS, nx=True) is None

                    output_event = {
                        "event_id": str(uuid.uuid4()),
                        "trace_id": trace_id,
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
                        # Increment counter (optional, for metrics)
                        count = r.incr(f"count:{fingerprint}")
                        r.expire(f"count:{fingerprint}", DEDUP_WINDOW_SECONDS) # Refresh TTL

                        output_event["type"] = "AlertDuplicateRejected"
                        output_event["payload"]["count"] = count
                        output_event["payload"]["decision"] = "rejected"

                        producer.send(OUTPUT_TOPIC_DUPLICATE, value=output_event)
                        logger.info(f"Duplicate rejected: {fingerprint} trace_id={trace_id}")
                    else:
                        # It's new (accepted)
                        # Initialize counter
                        r.set(f"count:{fingerprint}", 1, ex=DEDUP_WINDOW_SECONDS)

                        output_event["type"] = "AlertAccepted"
                        output_event["payload"]["decision"] = "accepted"

                        producer.send(OUTPUT_TOPIC_ACCEPTED, value=output_event)
                        logger.info(f"Alert accepted: {fingerprint} trace_id={trace_id}")

            producer.flush()

        except Exception as e:
            logger.error(f"Error in processing loop: {e}")
            time.sleep(1)

    logger.info("Worker stopped")
    producer.close()
    consumer.close()

if __name__ == "__main__":
    main()
