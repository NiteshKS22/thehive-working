from fastapi import FastAPI, HTTPException, Query
from opensearchpy import OpenSearch
import os

app = FastAPI(title="TheHive v5 Query Service")

# Configuration
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", 9200))
INDEX_PATTERN = "alerts-v1-*"

os_client = OpenSearch(
    hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
    http_compress=True,
    use_ssl=False
)

@app.get("/health")
def health_check():
    if os_client.ping():
        return {"status": "ok", "opensearch": "connected"}
    return {"status": "error", "opensearch": "disconnected"}

@app.get("/alerts")
def search_alerts(
    q: str = Query(None, description="Simple query string"),
    tenant_id: str = Query(..., description="Tenant ID (mandatory)"),
    size: int = 20,
    from_: int = 0
):
    # Enforce Tenant Isolation
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
        response = os_client.search(body=query_body, index=INDEX_PATTERN)
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

    response = os_client.search(body=query_body, index=INDEX_PATTERN)
    if not response["hits"]["hits"]:
        raise HTTPException(status_code=404, detail="Alert not found")

    return response["hits"]["hits"][0]["_source"]
