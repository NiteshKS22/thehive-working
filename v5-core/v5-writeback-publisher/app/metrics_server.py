from prometheus_client import Counter, start_http_server

EVENTS_PROCESSED = Counter('writeback_events_processed_total', 'Events processed', ['status'])
EVENTS_PUBLISHED = Counter('writeback_events_published_total', 'Events published to bridge', ['topic'])

def start_metrics_server(port=9012):
    start_http_server(port)
