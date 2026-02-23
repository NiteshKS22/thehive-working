import os
import sys
import time
import uuid
import json
import psycopg2
from kafka import KafkaProducer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
V4_DB_HOST = os.getenv("V4_DB_HOST", "postgres")
V4_DB_USER = os.getenv("V4_DB_USER", "hive")
V4_DB_PASSWORD = os.getenv("V4_DB_PASSWORD", "hive")
V4_DB_NAME = os.getenv("V4_DB_NAME", "thehive")

def verify():
    print("Verifying Writeback E2E...")

    # 1. Publish Mock v5 Event (Simulating Case Service)
    producer = KafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    case_id = f"case-{uuid.uuid4()}"
    event = {
        "event_id": str(uuid.uuid4()),
        "type": "CaseUpdated",
        "tenant_id": "T1",
        "payload": {
            "case_id": case_id,
            "title": "Writeback Test Case",
            "updated_at": int(time.time() * 1000)
        }
    }
    producer.send("cases.updated.v1", json.dumps(event).encode('utf-8'))
    producer.flush()
    print(f"Published v5 event for {case_id}")

    # 2. Wait for Inbox Row
    print("Waiting for v4 Inbox...")
    conn = psycopg2.connect(host=V4_DB_HOST, user=V4_DB_USER, password=V4_DB_PASSWORD, database=V4_DB_NAME)

    for _ in range(20):
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM v4_inbox WHERE entity_id = %s", (case_id,))
            row = cur.fetchone()
            if row:
                print(f"Found inbox row status: {row[0]}")
                if row[0] in ('APPLIED', 'PENDING', 'INFLIGHT'):
                    print("SUCCESS: Writeback event reached v4 inbox.")
                    return
        time.sleep(1)

    print("FAILURE: Inbox row not found.")
    sys.exit(1)

if __name__ == "__main__":
    verify()
