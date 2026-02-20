import os
import sys
import time
import json
import uuid
import psycopg2
from kafka import KafkaConsumer

# Env
DB_HOST = os.getenv("V4_DB_HOST", "localhost")
DB_USER = os.getenv("V4_DB_USER", "hive")
DB_PASS = os.getenv("V4_DB_PASSWORD", "hive")
DB_NAME = os.getenv("V4_DB_NAME", "thehive")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

def main():
    print("Verifying v4 Outbox Publisher...")

    # 1. Connect to DB and Insert PENDING Row
    try:
        conn = psycopg2.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, port=5432)
        cur = conn.cursor()

        event_id = str(uuid.uuid4())
        tenant_id = "test-tenant"
        agg_id = "case-123"

        cur.execute("""
            INSERT INTO v4_outbox (
                outbox_id, tenant_id, aggregate_type, aggregate_id, event_type, payload, created_at, available_at, status
            ) VALUES (
                %s, %s, 'CASE', %s, 'case.sync.v1', '{"title": "Test Case"}', 1000, 1000, 'PENDING'
            )
        """, (event_id, tenant_id, agg_id))
        conn.commit()
        print(f"Inserted Outbox ID: {event_id}")
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")
        sys.exit(1)

    # 2. Wait for Kafka Message
    consumer = KafkaConsumer(
        "bridge.v4.case.sync.v1",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        auto_offset_reset='earliest',
        consumer_timeout_ms=10000,
        group_id="verify-script"
    )

    print("Listening for Kafka message...")
    for msg in consumer:
        val = json.loads(msg.value)
        if val['event_id'] == event_id:
            print("SUCCESS: Received expected event from Kafka!")
            print(f"Key: {msg.key.decode('utf-8')}")
            if msg.key.decode('utf-8') != "test-tenant:CASE:case-123":
                print("FAILURE: Key mismatch")
                sys.exit(1)
            sys.exit(0)

    print("FAILURE: Timed out waiting for event.")
    sys.exit(1)

if __name__ == "__main__":
    main()
