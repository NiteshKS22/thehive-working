from prometheus_client import Counter, Gauge, start_http_server

OUTBOX_CLAIMED = Counter('outbox_rows_claimed_total', 'Rows claimed from outbox', ['service'])
OUTBOX_PUBLISHED = Counter('outbox_rows_published_total', 'Rows successfully published', ['service', 'topic'])
OUTBOX_FAILED = Counter('outbox_rows_failed_total', 'Rows failed to publish', ['service'])
OUTBOX_BACKLOG = Gauge('outbox_backlog_total', 'Current outbox backlog', ['service', 'status'])

def start_metrics_server(port=9011):
    start_http_server(port)
