import os
import json
import uuid
import time
import hashlib
import logging
import signal
import sys
import threading
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
import redis

# Mount Common Reliability
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../common')))
from reliability.dlq import build_dlq_event, send_dlq
from reliability.commit import commit_if_safe
from reliability.retry import execute_with_retry
from reliability.backpressure import check_backpressure

# Metrics
from metrics_server import start_metrics_server, MESSAGES_PROCESSED, DLQ_PUBLISHED, RETRIES_TOTAL, BACKPRESSURE_EVENTS, CONSUMER_LAG

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:29092")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
INPUT_TOPIC = "alerts.ingest.v1"
OUTPUT_TOPIC_ACCEPTED = "alerts.accepted.v1"
OUTPUT_TOPIC_DUPLICATE = "alerts.duplicate.v1"
DLQ_TOPIC = "alerts.ingest.dlq.v1"
DEDUP_WINDOW_SECONDS = int(os.getenv("DEDUP_WINDOW_SECONDS", 600))
AUTO_OFFSET_RESET = os.getenv("AUTO_OFFSET_RESET", "latest")
MAX_POLL_RECORDS = 100
METRICS_PORT = int(os.getenv("METRICS_PORT", 9001))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("dedup-worker")

running = True

def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def generate_fingerprint(payload, tenant_id):
    raw = f"{tenant_id}:{payload.get('source')}:{payload.get('type')}:{payload.get('sourceRef')}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def process_event(message, r, producer):
    event = message.value
    payload = event.get('payload', {})
    trace_id = event.get('trace_id')
    event_id = event.get('event_id')
    tenant_id = payload.get('tenant_id')

    if not tenant_id:
        raise ValueError("Missing tenant_id")

    fingerprint = generate_fingerprint(payload, tenant_id)
    redis_key = f"dedup:{tenant_id}:{fingerprint}"

    def redis_op():
        return r.set(redis_key, event_id, ex=DEDUP_WINDOW_SECONDS, nx=True)
    
    is_new = execute_with_retry(redis_op, max_retries=3, retryable_exceptions=(redis.ConnectionError, redis.TimeoutError))
    RETRIES_TOTAL.labels(service="dedup", operation="redis_set").inc()
    
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
        count = r.incr(f"count:{tenant_id}:{fingerprint}")
        r.expire(f"count:{tenant_id}:{fingerprint}", DEDUP_WINDOW_SECONDS)
        output_event["type"] = "AlertDuplicateRejected"
        output_event["payload"]["count"] = count
        output_event["payload"]["decision"] = "rejected"
        producer.send(OUTPUT_TOPIC_DUPLICATE, value=output_event)
    else:
        r.set(f"count:{tenant_id}:{fingerprint}", 1, ex=DEDUP_WINDOW_SECONDS)
        output_event["type"] = "AlertAccepted"
        output_event["payload"]["decision"] = "accepted"
        producer.send(OUTPUT_TOPIC_ACCEPTED, value=output_event)

    MESSAGES_PROCESSED.labels(service="dedup", topic=INPUT_TOPIC, status="success").inc()

def main():
    logger.info("Starting Dedup Worker (Phase 4.3)")
    start_metrics_server(METRICS_PORT)

    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        sys.exit(1)

    try:
        consumer = KafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id="dedup-group-v1",
            auto_offset_reset=AUTO_OFFSET_RESET,
            enable_auto_commit=False,
            max_poll_records=MAX_POLL_RECORDS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    except Exception as e:
        logger.error(f"Kafka connection failed: {e}")
        sys.exit(1)

    while running:
        start_time = time.time()
        try:
            msg_pack = consumer.poll(timeout_ms=1000)
            total_processed = 0
            for tp, messages in msg_pack.items():
                lag = 0 # Need highwater mark to calc real lag, simplified here
                CONSUMER_LAG.labels(service="dedup", topic=tp.topic, partition=tp.partition).set(lag) 
                
                for message in messages:
                    processing_success = False
                    dlq_success = False
                    
                    try:
                        execute_with_retry(lambda: process_event(message, r, producer), max_retries=3, retryable_exceptions=(redis.RedisError, KafkaError))
                        producer.flush()
                        processing_success = True
                    except Exception as e:
                        logger.error(f"Processing failed: {e}")
                        MESSAGES_PROCESSED.labels(service="dedup", topic=INPUT_TOPIC, status="error").inc()
                        
                        dlq_event = build_dlq_event(str(e), message.value, message.topic, message.partition, message.offset, message.value.get("payload", {}).get("tenant_id", "unknown"))
                        dlq_success = send_dlq(producer, DLQ_TOPIC, dlq_event)
                        if dlq_success:
                            DLQ_PUBLISHED.labels(service="dedup", topic=DLQ_TOPIC).inc()

                    if not commit_if_safe(consumer, processing_success, dlq_success):
                        break 
                    
                    total_processed += 1

            if total_processed > 0:
                check_backpressure(start_time, total_processed)
                BACKPRESSURE_EVENTS.labels(service="dedup").inc()

        except Exception as e:
            logger.error(f"Error in processing loop: {e}")
            time.sleep(1)

    producer.close()
    consumer.close()

if __name__ == "__main__":
    main()
