from prometheus_client import Counter, start_http_server

INBOX_ROWS_WRITTEN = Counter('inbox_rows_written_total', 'Inbox rows written', ['status'])
APPLY_SUCCESS = Counter('inbox_apply_success_total', 'Changes applied to v4', ['type'])
APPLY_CONFLICT = Counter('inbox_apply_conflict_total', 'Conflict detected', ['type'])

def start_metrics_server(port=9013):
    start_http_server(port)
