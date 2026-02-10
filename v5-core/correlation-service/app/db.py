import psycopg2
import logging
import os
from typing import Dict, Tuple, Optional, List

logger = logging.getLogger("correlation-db")

class Database:
    def __init__(self):
        self.conn = None
        self.host = os.getenv("POSTGRES_HOST", "postgres")
        self.port = int(os.getenv("POSTGRES_PORT", 5432))
        self.db = os.getenv("POSTGRES_DB", "v5_events")
        self.user = os.getenv("POSTGRES_USER", "hive")
        self.password = os.getenv("POSTGRES_PASSWORD", "hive")
        self._connect()

    def _connect(self):
        try:
            self.conn = psycopg2.connect(
                host=self.host, port=self.port, database=self.db, user=self.user, password=self.password
            )
            self.conn.autocommit = False
            logger.info("Connected to Postgres")
        except Exception as e:
            logger.error(f"Postgres connection failed: {e}")
            raise

    def process_correlation(self, group: Dict, link: Dict) -> Tuple[bool, bool, int, int]:
        """
        Atomically ensures group exists, inserts link, and updates group stats if link is new.
        Returns (is_new_group, is_new_link, new_count, new_severity).
        """
        try:
            with self.conn.cursor() as cur:
                # 1. Ensure Group Exists (Idempotent Insert)
                insert_group_query = """
                INSERT INTO correlation_groups (
                    tenant_id, group_id, correlation_key, rule_id, rule_name, confidence, status,
                    first_seen, last_seen, alert_count, max_severity, created_at, updated_at
                ) VALUES (
                    %(tenant_id)s, %(group_id)s, %(correlation_key)s, %(rule_id)s, %(rule_name)s, %(confidence)s, %(status)s,
                    %(first_seen)s, %(last_seen)s, 1, %(max_severity)s, %(first_seen)s, %(last_seen)s
                )
                ON CONFLICT (tenant_id, group_id) DO NOTHING
                RETURNING TRUE;
                """
                cur.execute(insert_group_query, group)
                is_new_group = bool(cur.fetchone())

                # 2. Insert Link
                insert_link_query = """
                INSERT INTO correlation_group_alert_links (
                    tenant_id, group_id, original_event_id, linked_at, link_reason
                ) VALUES (
                    %(tenant_id)s, %(group_id)s, %(original_event_id)s, %(linked_at)s, %(link_reason)s
                )
                ON CONFLICT (tenant_id, group_id, original_event_id) DO NOTHING
                RETURNING TRUE;
                """
                cur.execute(insert_link_query, link)
                is_new_link = bool(cur.fetchone())

                new_count = 1
                new_severity = group['max_severity']

                # 3. If Link is New AND Group was NOT new (it existed), we must update stats
                if is_new_link and not is_new_group:
                    update_group_query = """
                    UPDATE correlation_groups
                    SET
                        alert_count = alert_count + 1,
                        last_seen = GREATEST(last_seen, %(last_seen)s),
                        max_severity = GREATEST(max_severity, %(max_severity)s),
                        updated_at = %(last_seen)s
                    WHERE tenant_id = %(tenant_id)s AND group_id = %(group_id)s
                    RETURNING alert_count, max_severity;
                    """
                    cur.execute(update_group_query, group)
                    row = cur.fetchone()
                    if row:
                        new_count, new_severity = row

                self.conn.commit()
                return is_new_group, is_new_link, new_count, new_severity

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Process correlation failed: {e}")
            raise

    def fetch_rules(self) -> List[Dict]:
        """
        Fetch all active rules from correlation_rules table.
        """
        query = "SELECT rule_id, rule_name, enabled, confidence, window_minutes, correlation_key_template, required_fields FROM correlation_rules WHERE enabled = TRUE"
        try:
            # Reconnect if closed?
            if self.conn.closed:
                self._connect()

            with self.conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                rules = []
                for r in rows:
                    rules.append({
                        "rule_id": r[0],
                        "rule_name": r[1],
                        "enabled": r[2],
                        "confidence": r[3],
                        "window_minutes": r[4],
                        "correlation_key_template": r[5],
                        "required_fields": r[6] # Postgres ARRAY -> Python list
                    })
                return rules
        except Exception as e:
            logger.error(f"Fetch rules failed: {e}")
            return []

    def close(self):
        if self.conn:
            self.conn.close()
