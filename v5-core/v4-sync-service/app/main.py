import os
import sys
import json
import time
import logging
import signal
from kafka import KafkaConsumer, KafkaProducer
from opensearchpy import OpenSearch, helpers
from app.metrics_server import start_metrics_server, SYNC_EVENTS_PROCESSED, SYNC_CONFLICTS, DRIFT_DETECTED

# We assume 'common' is in PYTHONPATH (/app/common)
# If not (local dev), we try relative import
try:
    from common.reliability.retry import execute_with_retry
except ImportError:
    # Local dev fallback
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../common')))
    # from reliability.retry import execute_with_retry # (Mock if not available)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("v4-sync-service")

# Configuration
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:29092")
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", 9200))
OPENSEARCH_USE_SSL = os.getenv("OPENSEARCH_USE_SSL", "false").lower() == "true"
KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")

SYNC_CASE_TOPIC = "bridge.v4.case.sync.v1"
SYNC_ALERT_TOPIC = "bridge.v4.alert.sync.v1"
DRIFT_LOG_TOPIC = "bridge.drift.log.v1"
METRICS_PORT = int(os.getenv("METRICS_PORT", 9010))

running = True

def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def connect_kafka_consumer():
    return KafkaConsumer(
        SYNC_CASE_TOPIC,
        SYNC_ALERT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="v4-sync-group",
        auto_offset_reset='earliest',
        security_protocol=KAFKA_SECURITY_PROTOCOL,
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )

def connect_opensearch():
    return OpenSearch(
        hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
        http_compress=True,
        use_ssl=OPENSEARCH_USE_SSL,
        verify_certs=False # Self-signed in dev/internal
    )

def handle_case_sync(event, os_client, producer):
    payload = event.get('payload', {})
    tenant_id = event.get('tenant_id')
    case_id = payload.get('case_id')
    v4_updated_at = payload.get('updated_at', 0)

    if not tenant_id or not case_id:
        logger.error("Missing tenant_id or case_id in sync event")
        return

    try:
        existing = os_client.get(index="cases-v1", id=f"{tenant_id}:{case_id}")
        existing_source = existing['_source']
        v5_updated_at = existing_source.get('updated_at', 0)

        if v5_updated_at > v4_updated_at:
            logger.warning(f"Conflict: v5 state is newer than v4 sync event. Case {case_id}. v5={v5_updated_at}, v4={v4_updated_at}")
            SYNC_CONFLICTS.labels(type="case").inc()
            drift_event = {
                "type": "DriftDetected",
                "resource": f"case:{case_id}",
                "tenant": tenant_id,
                "reason": "v5_newer_than_v4_sync",
                "timestamp": int(time.time()*1000)
            }
            producer.send(DRIFT_LOG_TOPIC, json.dumps(drift_event).encode('utf-8'))
            return

        if v5_updated_at == v4_updated_at:
            return

    except Exception:
        pass

    doc = payload.copy()
    doc['tenant_id'] = tenant_id
    doc['synced_from_v4'] = True
    doc['sync_timestamp'] = int(time.time() * 1000)

    try:
        os_client.index(
            index="cases-v1",
            id=f"{tenant_id}:{case_id}",
            body=doc,
            refresh=True
        )
        logger.info(f"Synced Case {case_id} from v4 (Tenant: {tenant_id})")
        SYNC_EVENTS_PROCESSED.labels(type="case", status="success").inc()
    except Exception as e:
        logger.error(f"Failed to sync case {case_id}: {e}")
        SYNC_EVENTS_PROCESSED.labels(type="case", status="error").inc()
        raise e

def handle_alert_sync(event, os_client, producer):
    payload = event.get('payload', {})
    tenant_id = event.get('tenant_id')
    alert_id = payload.get('alert_id') # v4 ID
    v4_updated_at = payload.get('updated_at', 0)

    if not tenant_id or not alert_id:
        logger.error("Missing tenant_id or alert_id in sync event")
        return

    # Check existence
    try:
        # We assume alerts are indexed by v4 ID or a mapping exists.
        # For bridge phase, we use v4 ID as document ID if possible, or query by original_event_id logic.
        # Here we use v4 ID directly for sync simplicity as per design B1_2.
        existing = os_client.get(index="alerts-v1", id=f"{tenant_id}:{alert_id}")
        existing_source = existing['_source']
        v5_updated_at = existing_source.get('updated_at', 0)

        if v5_updated_at > v4_updated_at:
            logger.warning(f"Conflict: v5 alert newer. Alert {alert_id}")
            SYNC_CONFLICTS.labels(type="alert").inc()
            drift_event = {
                "type": "DriftDetected",
                "resource": f"alert:{alert_id}",
                "tenant": tenant_id,
                "reason": "v5_newer_than_v4_sync",
                "timestamp": int(time.time()*1000)
            }
            producer.send(DRIFT_LOG_TOPIC, json.dumps(drift_event).encode('utf-8'))
            return

        if v5_updated_at == v4_updated_at:
            return

    except Exception:
        pass

    doc = payload.copy()
    doc['tenant_id'] = tenant_id
    doc['synced_from_v4'] = True
    doc['sync_timestamp'] = int(time.time() * 1000)

    try:
        os_client.index(
            index="alerts-v1", # Might need time-based routing logic in real impl
            id=f"{tenant_id}:{alert_id}",
            body=doc,
            refresh=True
        )
        logger.info(f"Synced Alert {alert_id} from v4 (Tenant: {tenant_id})")
        SYNC_EVENTS_PROCESSED.labels(type="alert", status="success").inc()
    except Exception as e:
        logger.error(f"Failed to sync alert {alert_id}: {e}")
        SYNC_EVENTS_PROCESSED.labels(type="alert", status="error").inc()
        raise e

def main():
    logger.info("Starting v4 Sync Service (Bridge Layer) with TLS Support")
    start_metrics_server(METRICS_PORT)

    os_client = connect_opensearch()

    try:
        consumer = connect_kafka_consumer()
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            security_protocol=KAFKA_SECURITY_PROTOCOL
        )
    except Exception as e:
        logger.error(f"Failed to connect to Kafka: {e}")
        sys.exit(1)

    while running:
        msg_pack = consumer.poll(timeout_ms=1000)
        for tp, messages in msg_pack.items():
            for message in messages:
                try:
                    event = message.value
                    event_type = event.get('type')

                    if event_type == 'case.sync.v1':
                        handle_case_sync(event, os_client, producer)
                    elif event_type == 'alert.sync.v1':
                        handle_alert_sync(event, os_client, producer)
                    else:
                        logger.debug(f"Unknown event type: {event_type}")

                except Exception as e:
                    logger.error(f"Error processing message: {e}")

    consumer.close()
    producer.close()

if __name__ == "__main__":
    main()
