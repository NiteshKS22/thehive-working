import os
import json
import logging
import signal
import sys
import time
from kafka import KafkaConsumer
from opensearchpy import OpenSearch, helpers

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:29092")
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", 9200))
INPUT_TOPIC = "alerts.accepted.v1"
INDEX_PREFIX = "alerts-v1"

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("indexer-worker")

running = True

def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    logger.info("Starting OpenSearch Indexer Worker")

    # Initialize OpenSearch
    os_client = OpenSearch(
        hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
        http_compress=True,
        use_ssl=False
    )

    # Initialize Kafka Consumer
    try:
        consumer = KafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id="indexer-group-v1",
            auto_offset_reset='earliest',
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        logger.info("Connected to Kafka/Redpanda")
    except Exception as e:
        logger.error(f"Kafka connection failed: {e}")
        sys.exit(1)

    while running:
        try:
            msg_pack = consumer.poll(timeout_ms=1000)
            actions = []

            for tp, messages in msg_pack.items():
                for message in messages:
                    event = message.value
                    payload = event.get('payload', {})
                    trace_id = event.get('trace_id')

                    # Flatten/Transform for Indexing
                    doc = {
                        "event_id": event.get('event_id'),
                        "trace_id": trace_id,
                        "timestamp": event.get('timestamp'),
                        "tenant_id": payload.get('tenant_id', 'default'), # Default for single-tenant
                        "fingerprint": payload.get('fingerprint'),
                        "status": payload.get('decision'),
                    }

                    # Merge original alert data
                    original_payload = payload.get('original_payload', {})
                    doc.update(original_payload)

                    # Bulk Action
                    action = {
                        "_index": f"{INDEX_PREFIX}-{time.strftime('%Y.%m')}", # Monthly indices
                        "_id": payload.get('original_event_id'), # Use original_event_id to avoid overwriting distinct alerts with same fingerprint
                        "_source": doc
                    }
                    actions.append(action)

            if actions:
                success, failed = helpers.bulk(os_client, actions, stats_only=True)
                logger.info(f"Indexed {success} documents. Failed: {failed}")

        except Exception as e:
            logger.error(f"Error in indexing loop: {e}")
            time.sleep(1)

    logger.info("Worker stopped")
    consumer.close()

if __name__ == "__main__":
    main()
