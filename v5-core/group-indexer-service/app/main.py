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
INDEX_NAME = "groups-v1"

# Topics
TOPICS = ["correlation.group.created.v1", "correlation.group.updated.v1"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("group-indexer")

running = True

def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    logger.info("Starting Group Indexer Worker")

    os_client = OpenSearch(
        hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
        http_compress=True,
        use_ssl=False
    )

    try:
        consumer = KafkaConsumer(
            *TOPICS,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id="group-indexer-v1",
            auto_offset_reset='latest', # Or earliest for replay
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        logger.info(f"Connected to Kafka, consuming: {TOPICS}")
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
                    tenant_id = event.get('tenant_id')
                    group_id = payload.get('group_id')

                    if not tenant_id or not group_id:
                        continue

                    # Prepare doc
                    doc = payload.copy()
                    doc['tenant_id'] = tenant_id

                    # Ensure timestamp fields are properly formatted if needed
                    # OpenSearch handles numbers as dates if mapping set to epoch_millis.
                    # Payload has first_seen/last_seen as integers (ms). Correct.

                    # Generate deterministic _id
                    doc_id = f"{tenant_id}:{group_id}"

                    action = {
                        "_op_type": "update",
                        "_index": INDEX_NAME,
                        "_id": doc_id,
                        "doc": doc,
                        "doc_as_upsert": True
                    }
                    actions.append(action)

            if actions:
                success, failed = helpers.bulk(os_client, actions, stats_only=True)
                logger.info(f"Indexed {success} groups. Failed: {failed}")

        except Exception as e:
            logger.error(f"Error in indexing loop: {e}")
            time.sleep(1)

    logger.info("Worker stopped")
    consumer.close()

if __name__ == "__main__":
    main()
