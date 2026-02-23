import os
import psycopg2
import logging

logger = logging.getLogger("inbox-db")

def get_db_conn():
    return psycopg2.connect(
        host=os.getenv("V4_DB_HOST", "postgres"),
        database=os.getenv("V4_DB_NAME", "thehive"),
        user=os.getenv("V4_DB_USER", "hive"),
        password=os.getenv("V4_DB_PASSWORD", "hive"),
        port=int(os.getenv("V4_DB_PORT", 5432))
    )

def insert_inbox_row(row_data):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO v4_inbox
                (id, tenant_id, entity_type, entity_id, source_event_id, origin, payload_json, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING', %s, %s)
                ON CONFLICT (tenant_id, entity_type, entity_id, source_event_id) DO NOTHING
            """, (
                row_data['id'], row_data['tenant_id'], row_data['entity_type'],
                row_data['entity_id'], row_data['source_event_id'], row_data['origin'],
                row_data['payload_json'], row_data['created_at'], row_data['created_at']
            ))
        conn.commit()
    finally:
        conn.close()

def claim_pending_rows(limit=50):
    conn = get_db_conn()
    rows = []
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT * FROM v4_inbox
                WHERE status = 'PENDING'
                ORDER BY created_at ASC
                LIMIT {limit}
                FOR UPDATE SKIP LOCKED
            """)
            # Fetch as tuples, need to map to dict ideally or use index
            # Simplified for B1.3
            colnames = [desc[0] for desc in cur.description]
            for row in cur.fetchall():
                rows.append(dict(zip(colnames, row)))

            if rows:
                ids = [r['id'] for r in rows]
                placeholders = ','.join(['%s'] * len(ids))
                cur.execute(f"UPDATE v4_inbox SET status = 'INFLIGHT' WHERE id IN ({placeholders})", tuple(ids))
        conn.commit()
    finally:
        conn.close()
    return rows

def mark_applied(row_id):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE v4_inbox SET status = 'APPLIED' WHERE id = %s", (row_id,))
        conn.commit()
    finally:
        conn.close()

def mark_conflict(row_id, reason):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE v4_inbox SET status = 'CONFLICT', last_error = %s WHERE id = %s", (reason, row_id))
        conn.commit()
    finally:
        conn.close()
