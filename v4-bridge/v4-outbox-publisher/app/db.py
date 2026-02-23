import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger("outbox-db")

def get_db_conn():
    return psycopg2.connect(
        host=os.getenv("V4_DB_HOST", "postgres"),
        database=os.getenv("V4_DB_NAME", "thehive"),
        user=os.getenv("V4_DB_USER", "hive"),
        password=os.getenv("V4_DB_PASSWORD", "hive"),
        port=int(os.getenv("V4_DB_PORT", 5432))
    )

def claim_outbox_rows(limit=100):
    """
    Claims PENDING rows using SKIP LOCKED.
    Returns list of dicts.
    """
    conn = get_db_conn()
    rows = []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Select and lock
            cur.execute(f"""
                SELECT * FROM v4_outbox
                WHERE status = 'PENDING' AND available_at <= (extract(epoch from now()) * 1000)::bigint
                ORDER BY created_at ASC
                LIMIT {limit}
                FOR UPDATE SKIP LOCKED
            """)
            rows = cur.fetchall()

            # If we found rows, we keep the transaction open?
            # No, for simplicity in this implementation, we will mark them as INFLIGHT immediately
            # so we can release the DB lock, then process, then update to PUBLISHED.
            # OR we keep connection open.
            # Better pattern: Mark INFLIGHT.

            if rows:
                ids = [str(r['outbox_id']) for r in rows]
                placeholders = ','.join(['%s'] * len(ids))
                cur.execute(f"""
                    UPDATE v4_outbox SET status = 'INFLIGHT', publish_attempts = publish_attempts + 1
                    WHERE outbox_id IN ({placeholders})
                """, tuple(ids))
                conn.commit()
    except Exception as e:
        logger.error(f"DB Claim error: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()

    return rows

def mark_published(outbox_id):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE v4_outbox
                SET status = 'PUBLISHED', published_at = (extract(epoch from now()) * 1000)::bigint
                WHERE outbox_id = %s
            """, (outbox_id,))
        conn.commit()
    finally:
        conn.close()

def mark_failed(outbox_id, error):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            # Backoff logic could be added here
            cur.execute("""
                UPDATE v4_outbox
                SET status = 'PENDING', last_error = %s, available_at = available_at + 5000
                WHERE outbox_id = %s
            """, (str(error), outbox_id))
        conn.commit()
    finally:
        conn.close()
