from fastapi import FastAPI, HTTPException, Query, Body
from opensearchpy import OpenSearch
import os
import psycopg2
import time
import hashlib
import itertools
from typing import List, Optional, Dict, Any

app = FastAPI(title="TheHive v5 Query Service")

# Configuration
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", 9200))
INDEX_ALERTS = "alerts-v1-*"
INDEX_GROUPS = "groups-v1"

# Postgres Config
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_PORT = int(os.getenv("POSTGRES_PORT", 5432))
PG_DB = os.getenv("POSTGRES_DB", "v5_events")
PG_USER = os.getenv("POSTGRES_USER", "hive")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "hive")

os_client = OpenSearch(
    hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
    http_compress=True,
    use_ssl=False
)

def get_db_conn():
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, database=PG_DB, user=PG_USER, password=PG_PASSWORD
        )
        return conn
    except Exception as e:
        print(f"DB Connection failed: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

@app.get("/health")
def health_check():
    os_status = "connected" if os_client.ping() else "disconnected"
    pg_status = "disconnected"
    try:
        conn = get_db_conn()
        conn.close()
        pg_status = "connected"
    except:
        pass

    return {"status": "ok", "opensearch": os_status, "postgres": pg_status}

@app.get("/alerts")
def search_alerts(
    q: str = Query(None, description="Simple query string"),
    tenant_id: str = Query(..., description="Tenant ID (mandatory)"),
    size: int = 20,
    from_: int = 0
):
    query_body = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"tenant_id": tenant_id}}
                ]
            }
        },
        "from": from_,
        "size": size,
        "sort": [{"timestamp": "desc"}]
    }

    if q:
        query_body["query"]["bool"]["must"] = [
            {"query_string": {"query": q}}
        ]

    try:
        response = os_client.search(body=query_body, index=INDEX_ALERTS)
        return {
            "total": response["hits"]["total"]["value"],
            "hits": [hit["_source"] for hit in response["hits"]["hits"]]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str, tenant_id: str = Query(...)):
    query_body = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"tenant_id": tenant_id}},
                    {"ids": {"values": [alert_id]}}
                ]
            }
        }
    }

    response = os_client.search(body=query_body, index=INDEX_ALERTS)
    if not response["hits"]["hits"]:
        raise HTTPException(status_code=404, detail="Alert not found")

    return response["hits"]["hits"][0]["_source"]

@app.get("/groups")
def search_groups(
    q: str = Query(None, description="Query string for groups"),
    tenant_id: str = Query(..., description="Tenant ID (mandatory)"),
    status: Optional[str] = Query(None, regex="^(OPEN|CLOSED|MERGED)$"),
    size: int = 20,
    from_: int = 0
):
    query_body = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"tenant_id": tenant_id}}
                ]
            }
        },
        "from": from_,
        "size": size,
        "sort": [{"last_seen": "desc"}]
    }

    if status:
        query_body["query"]["bool"]["filter"].append({"term": {"status": status}})

    if q:
        query_body["query"]["bool"]["must"] = [
            {"query_string": {"query": q}}
        ]

    try:
        response = os_client.search(body=query_body, index=INDEX_GROUPS)
        return {
            "total": response["hits"]["total"]["value"],
            "hits": [hit["_source"] for hit in response["hits"]["hits"]]
        }
    except Exception as e:
        if "index_not_found_exception" in str(e):
             return {"total": 0, "hits": []}
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/groups/{group_id}")
def get_group(group_id: str, tenant_id: str = Query(...)):
    doc_id = f"{tenant_id}:{group_id}"
    try:
        response = os_client.get(index=INDEX_GROUPS, id=doc_id)
        if response["_source"]["tenant_id"] != tenant_id:
             raise HTTPException(status_code=404, detail="Group not found")

        # Enrich with rule metadata?
        # Ideally stored in OpenSearch, but if we want fresh rule info:
        group_data = response["_source"]
        rule_id = group_data.get("rule_id")
        if rule_id:
            conn = get_db_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT rule_name, confidence, window_minutes FROM correlation_rules WHERE rule_id = %s", (rule_id,))
                    row = cur.fetchone()
                    if row:
                        group_data["_rule_metadata"] = {
                            "name": row[0],
                            "confidence": row[1],
                            "window": row[2]
                        }
            except:
                pass
            finally:
                conn.close()

        return group_data
    except Exception as e:
        if "index_not_found_exception" in str(e) or "NotFoundError" in str(e):
            raise HTTPException(status_code=404, detail="Group not found")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/groups/{group_id}/alerts")
def get_group_alerts(group_id: str, tenant_id: str = Query(...)):
    conn = get_db_conn()
    links = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT original_event_id, linked_at, link_reason FROM correlation_group_alert_links WHERE tenant_id = %s AND group_id = %s ORDER BY linked_at ASC",
                (tenant_id, group_id)
            )
            rows = cur.fetchall()
            for r in rows:
                links.append({"id": r[0], "linked_at": r[1], "reason": r[2]})
    finally:
        conn.close()

    if not links:
        return {"total": 0, "hits": []}

    alert_ids = [l["id"] for l in links]
    os_docs = {}
    try:
        query_body = {
            "query": {
                "ids": {
                    "values": alert_ids
                }
            },
            "size": len(alert_ids)
        }
        resp = os_client.search(body=query_body, index=INDEX_ALERTS)
        for hit in resp["hits"]["hits"]:
            os_docs[hit["_id"]] = hit["_source"]
    except Exception as e:
        print(f"Failed to fetch alert details: {e}")

    results = []
    for link in links:
        aid = link["id"]
        detail = os_docs.get(aid, {})
        detail["_link_info"] = {
            "linked_at": link["linked_at"],
            "reason": link["reason"]
        }
        results.append(detail)

    return {"total": len(results), "hits": results}

@app.get("/rules")
def list_rules():
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            # Return all rules (enabled/disabled)
            cur.execute("SELECT rule_id, rule_name, enabled, confidence, window_minutes, correlation_key_template, required_fields FROM correlation_rules ORDER BY rule_id")
            rows = cur.fetchall()
            rules = []
            for r in rows:
                rules.append({
                    "rule_id": r[0],
                    "rule_name": r[1],
                    "enabled": r[2],
                    "confidence": r[3],
                    "window_minutes": r[4],
                    "template": r[5],
                    "required_fields": r[6]
                })
            return {"total": len(rules), "rules": rules}
    finally:
        conn.close()

@app.post("/rules/simulate")
def simulate_rules(
    alert_payload: Dict[str, Any] = Body(...),
    tenant_id: str = Query(..., description="Tenant ID to simulate context")
):
    # Dry-run simulation
    conn = get_db_conn()
    rules = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT rule_id, rule_name, enabled, confidence, window_minutes, correlation_key_template, required_fields FROM correlation_rules WHERE enabled = TRUE")
            rows = cur.fetchall()
            for r in rows:
                rules.append({
                    "rule_id": r[0],
                    "rule_name": r[1],
                    "confidence": r[3],
                    "window_minutes": r[4],
                    "template": r[5],
                    "required_fields": r[6]
                })
    finally:
        conn.close()

    timestamp = int(time.time() * 1000)
    matches = []

    context = {"tenant_id": [tenant_id]}
    for k, v in alert_payload.items():
        if isinstance(v, list):
            context[k] = v
        else:
            context[k] = [v]

    for rule in rules:
        iterables = {}
        missing = False
        for field in rule['required_fields']:
            if field not in context or not context[field]:
                missing = True
                break
            iterables[field] = context[field]

        if missing:
            continue

        keys = list(iterables.keys())
        values_product = itertools.product(*(iterables[k] for k in keys))

        for combination in values_product:
            local_ctx = dict(zip(keys, combination))
            try:
                key = rule['template'].format(**local_ctx)

                window_ms = rule['window_minutes'] * 60 * 1000
                window_idx = int(timestamp / window_ms) if window_ms > 0 else 0
                raw_id = f"{tenant_id}:{rule['rule_id']}:{key}:{window_idx}"
                group_id = hashlib.sha256(raw_id.encode('utf-8')).hexdigest()

                matches.append({
                    "rule_id": rule['rule_id'],
                    "rule_name": rule['rule_name'],
                    "correlation_key": key,
                    "group_id": group_id,
                    "window_idx": window_idx
                })
            except:
                continue

    return {"matches": matches}
