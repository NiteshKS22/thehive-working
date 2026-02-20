from prometheus_client import Counter, Gauge, start_http_server

# Metrics for Sync Service
SYNC_EVENTS_PROCESSED = Counter('bridge_sync_events_processed_total', 'Total sync events processed', ['type', 'status'])
SYNC_CONFLICTS = Counter('bridge_sync_conflicts_total', 'Total conflicts detected', ['type'])
DRIFT_DETECTED = Counter('bridge_drift_detected_total', 'Total drift incidents detected', ['resource_type'])
CONSUMER_LAG = Gauge('bridge_consumer_lag', 'Kafka consumer lag', ['topic', 'partition'])

def start_metrics_server(port=9010):
    start_http_server(port)
