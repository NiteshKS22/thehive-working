import os
import sys
import uuid
import time
import json
import psycopg2

# Env
DB_HOST = os.getenv("V4_DB_HOST", "postgres")
DB_USER = os.getenv("V4_DB_USER", "hive")
DB_PASS = os.getenv("V4_DB_PASSWORD", "hive")
DB_NAME = os.getenv("V4_DB_NAME", "thehive")

def seed():
    print("Seeding v4 Outbox...")
    try:
        conn = psycopg2.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, port=5432)
        cur = conn.cursor()

        now = int(time.time() * 1000)

        # 1. Standard Case (Tenant A)
        case_id_a = "case-A-100"
        tenant_a = "tenant-A"
        cur.execute("""
            INSERT INTO v4_outbox (outbox_id, tenant_id, aggregate_type, aggregate_id, event_type, payload, created_at, available_at, status)
            VALUES (%s, %s, 'CASE', %s, 'case.sync.v1', %s, %s, %s, 'PENDING')
        """, (str(uuid.uuid4()), tenant_a, case_id_a, json.dumps({
            "case_id": case_id_a, "title": "Bridge Case A", "severity": 3, "status": "Open", "updated_at": now
        }), now, now))

        # 2. Alert (Tenant A)
        alert_id_a = "alert-A-200"
        cur.execute("""
            INSERT INTO v4_outbox (outbox_id, tenant_id, aggregate_type, aggregate_id, event_type, payload, created_at, available_at, status)
            VALUES (%s, %s, 'ALERT', %s, 'alert.sync.v1', %s, %s, %s, 'PENDING')
        """, (str(uuid.uuid4()), tenant_a, alert_id_a, json.dumps({
            "alert_id": alert_id_a, "title": "Bridge Alert A", "source": "test", "updated_at": now
        }), now, now))

        # 3. Duplicate Case Event (Idempotency Test) - same data, new event ID
        # Wait 1ms to ensure order
        time.sleep(0.001)
        cur.execute("""
            INSERT INTO v4_outbox (outbox_id, tenant_id, aggregate_type, aggregate_id, event_type, payload, created_at, available_at, status)
            VALUES (%s, %s, 'CASE', %s, 'case.sync.v1', %s, %s, %s, 'PENDING')
        """, (str(uuid.uuid4()), tenant_a, case_id_a, json.dumps({
            "case_id": case_id_a, "title": "Bridge Case A", "severity": 3, "status": "Open", "updated_at": now
        }), now + 1, now + 1))

        # 4. Tenant B Case (Isolation Test)
        case_id_b = "case-B-300"
        tenant_b = "tenant-B"
        cur.execute("""
            INSERT INTO v4_outbox (outbox_id, tenant_id, aggregate_type, aggregate_id, event_type, payload, created_at, available_at, status)
            VALUES (%s, %s, 'CASE', %s, 'case.sync.v1', %s, %s, %s, 'PENDING')
        """, (str(uuid.uuid4()), tenant_b, case_id_b, json.dumps({
            "case_id": case_id_b, "title": "Bridge Case B", "severity": 1, "status": "Open", "updated_at": now
        }), now, now))

        conn.commit()
        print("Seeding complete.")
        conn.close()

    except Exception as e:
        print(f"Seeding failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    seed()
