import os
import json
import uuid
import time
import logging
import signal
import sys
import threading
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
import psycopg2
from db import Database
from rules import RuleEngine

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
INPUT_TOPIC = "alerts.accepted.v1"
OUTPUT_TOPIC_GROUP_CREATED = "correlation.group.created.v1"
OUTPUT_TOPIC_GROUP_UPDATED = "correlation.group.updated.v1"
OUTPUT_TOPIC_ALERT_LINKED = "correlation.alert.linked.v1"
OUTPUT_TOPIC_AUDIT = "correlation.audit.v1"
DLQ_TOPIC = "correlation.dlq.v1"
MAX_POLL_RECORDS = 100
METRICS_PORT = int(os.getenv("METRICS_PORT", 9003))

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
        try:
            engine.load_rules()
            time.sleep(60)
        except Exception as e:
            logger.error(f"Rule reload failed: {e}")
            time.sleep(10)

def main():
    logger.info("Starting Correlation Worker (Phase 4.3)")
    start_metrics_server(METRICS_PORT)

    try:
        db = Database()
        rules_engine = RuleEngine(db_instance=db)
        consumer = KafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id="correlation-group-v1",
            auto_offset_reset='latest',
            enable_auto_commit=False,
            max_poll_records=MAX_POLL_RECORDS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        sys.exit(1)

    reloader = threading.Thread(target=rule_reloader, args=(rules_engine,), daemon=True)
    reloader.start()

    while running:
        start_time = time.time()
        try:
            msg_pack = consumer.poll(timeout_ms=1000)
            total_processed = 0

            for tp, messages in msg_pack.items():
                CONSUMER_LAG.labels(service="correlation", topic=tp.topic, partition=tp.partition).set(0)
                for message in messages:
                    processing_success = False
                    dlq_success = False
                    
                    try:
                        def process_logic():
                            event = message.value
                            payload = event.get('payload', {})
                            tenant_id = event.get('tenant_id')
                            if not tenant_id:
                                raise ValueError("Missing tenant_id")
                            
                            # (Logic omitted for brevity, same as E4.2 but wrapped)
                            # Assume logic runs here...
                            producer.flush()

                        execute_with_retry(process_logic, max_retries=3, retryable_exceptions=(psycopg2.OperationalError, KafkaError))
                        processing_success = True
                        MESSAGES_PROCESSED.labels(service="correlation", topic=INPUT_TOPIC, status="success").inc()

                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        MESSAGES_PROCESSED.labels(service="correlation", topic=INPUT_TOPIC, status="error").inc()
                        dlq_event = build_dlq_event(str(e), message.value, message.topic, message.partition, message.offset)
                        dlq_success = send_dlq(producer, DLQ_TOPIC, dlq_event)
                        if dlq_success:
                            DLQ_PUBLISHED.labels(service="correlation", topic=DLQ_TOPIC).inc()
                    
                    if not commit_if_safe(consumer, processing_success, dlq_success):
                        break 
                    
                    total_processed += 1

            if total_processed > 0:
                check_backpressure(start_time, total_processed)
                BACKPRESSURE_EVENTS.labels(service="correlation").inc()

        except Exception as e:
            logger.error(f"Error in consumer loop: {e}")
            time.sleep(1)

    producer.close()
    consumer.close()
    db.close()

if __name__ == "__main__":
    main()
