from fastapi import FastAPI, HTTPException, Query
from opensearchpy import OpenSearch
import os
import psycopg2
from typing import List, Optional

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
        # Search groups index
        response = os_client.search(body=query_body, index=INDEX_GROUPS)
        return {
            "total": response["hits"]["total"]["value"],
            "hits": [hit["_source"] for hit in response["hits"]["hits"]]
        }
    except Exception as e:
        # Index might not exist yet
        if "index_not_found_exception" in str(e):
             return {"total": 0, "hits": []}
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/groups/{group_id}")
def get_group(group_id: str, tenant_id: str = Query(...)):
    # Fetch from OpenSearch for fast read (or DB for strict consistency?)
    # Architecture says "OpenSearch projection for groups... for fast UI queries".
    # Use OpenSearch.

    doc_id = f"{tenant_id}:{group_id}"
    try:
        response = os_client.get(index=INDEX_GROUPS, id=doc_id)
        # Verify tenant_id in doc (redundant if ID constructed with tenant, but safe)
        if response["_source"]["tenant_id"] != tenant_id:
             raise HTTPException(status_code=404, detail="Group not found")
        return response["_source"]
    except Exception as e:
        if "index_not_found_exception" in str(e):
            raise HTTPException(status_code=404, detail="Group not found")
        if "NotFoundError" in str(e) or "not_found" in str(e): # opensearch-py specific
             raise HTTPException(status_code=404, detail="Group not found")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/groups/{group_id}/alerts")
def get_group_alerts(group_id: str, tenant_id: str = Query(...)):
    # 1. Fetch Links from Postgres (Authoritative Timeline)
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

    # 2. Fetch Alert Details from OpenSearch
    alert_ids = [l["id"] for l in links]

    # We can't guarantee all alerts are indexed yet (race condition), but usually they are (indexer is fast).
    # Use ids query.
    # Note: _id in indexer is original_event_id.

    os_docs = {}
    try:
        # mget requires index, but we have wildcard. Use search with ids filter.
        # Fetch in batches if large? Assuming < 1000 alerts per group for now.
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
        # Continue with missing details?

    # 3. Merge
    results = []
    for link in links:
        aid = link["id"]
        detail = os_docs.get(aid, {})
        # Merge link info
        detail["_link_info"] = {
            "linked_at": link["linked_at"],
            "reason": link["reason"]
        }
        results.append(detail)

    return {"total": len(results), "hits": results}
