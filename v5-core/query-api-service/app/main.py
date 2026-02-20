import time
import uuid
import json
import logging
import sys
import os
import psycopg2
import hashlib
import itertools
from fastapi import FastAPI, HTTPException, Response, status, Depends, Body, Query
from opensearchpy import OpenSearch
from typing import Dict, Any, Optional, List

# Mount Common Auth
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../common')))
from auth.middleware import get_auth_context, AuthContext, validate_auth_config, require_permission
from auth.rbac import PERM_ALERT_READ, PERM_CASE_READ, PERM_RULE_SIMULATE
from observability.metrics import MetricsMiddleware, get_metrics_response
from observability.health import global_health_registry

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("query-service")

app = FastAPI(title="TheHive v5 Query Service")

app.add_middleware(MetricsMiddleware, service_name="query-api-service")

@app.on_event("startup")
def startup_event():
    validate_auth_config()
    
    def check_os():
        return os_client.ping()
        
    def check_pg():
        try:
            conn = get_db_conn()
            conn.close()
            return True
        except:
            return False
            
    global_health_registry.add_check("opensearch", check_os)
    global_health_registry.add_check("postgres", check_pg)

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

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/readyz")
def readyz():
    result = global_health_registry.check_health()
    if result["status"] != "ok":
        return Response(content=json.dumps(result), status_code=503, media_type="application/json")
    return result

@app.get("/metrics")
def metrics():
    return get_metrics_response()

@app.get("/health")
def health_check():
    return healthz()

@app.get("/alerts")
def search_alerts(
    q: str = Query(None, description="Simple query string"),
    size: int = 20,
    from_: int = 0,
    auth: AuthContext = Depends(require_permission(PERM_ALERT_READ))
):
    query_body = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"tenant_id": auth.tenant_id}}
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
def get_alert(alert_id: str, auth: AuthContext = Depends(require_permission(PERM_ALERT_READ))):
    query_body = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"tenant_id": auth.tenant_id}},
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
    status: Optional[str] = Query(None, regex="^(OPEN|CLOSED|MERGED)$"),
    size: int = 20,
    from_: int = 0,
    auth: AuthContext = Depends(require_permission(PERM_CASE_READ))
):
    query_body = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"tenant_id": auth.tenant_id}}
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
def get_group(group_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    doc_id = f"{auth.tenant_id}:{group_id}"
    try:
        response = os_client.get(index=INDEX_GROUPS, id=doc_id)
        if response["_source"]["tenant_id"] != auth.tenant_id:
             raise HTTPException(status_code=404, detail="Group not found")

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
def get_group_alerts(group_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    conn = get_db_conn()
    links = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT original_event_id, linked_at, link_reason FROM correlation_group_alert_links WHERE tenant_id = %s AND group_id = %s ORDER BY linked_at ASC",
                (auth.tenant_id, group_id)
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
            source = hit["_source"]
            if source.get("tenant_id") == auth.tenant_id:
                os_docs[hit["_id"]] = source

    except Exception as e:
        print(f"Failed to fetch alert details: {e}")

    results = []
    for link in links:
        aid = link["id"]
        detail = os_docs.get(aid, {})
        if detail:
            detail["_link_info"] = {
                "linked_at": link["linked_at"],
                "reason": link["reason"]
            }
            results.append(detail)

    return {"total": len(results), "hits": results}

@app.get("/rules")
def list_rules(auth: AuthContext = Depends(require_permission(PERM_RULE_SIMULATE))):
    # Assuming rules are global read, but authenticated
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
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
    auth: AuthContext = Depends(require_permission(PERM_RULE_SIMULATE)) # Require Auth, implicit Tenant
):
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

    context = {"tenant_id": [auth.tenant_id]} # Force tenant from auth
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
                raw_id = f"{auth.tenant_id}:{rule['rule_id']}:{key}:{window_idx}"
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

# E3: Case Domain Read Endpoints (Proxied to Query API for unified read surface)
# Implementation: Direct Postgres Read
@app.get("/cases")
def list_cases(
    status: Optional[str] = Query(None, regex="^(OPEN|CLOSED)$"),
    severity: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
    auth: AuthContext = Depends(require_permission(PERM_CASE_READ))
):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            query = "SELECT case_id, title, status, severity, created_at, updated_at, assigned_to FROM cases WHERE tenant_id = %s"
            params = [auth.tenant_id]
            
            if status:
                query += " AND status = %s"
                params.append(status)
            if severity:
                query += " AND severity = %s"
                params.append(severity)
            
            query += " ORDER BY updated_at DESC LIMIT %s OFFSET %s"
            params.append(limit)
            params.append(offset)
            
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            
            cases = []
            for r in rows:
                cases.append({
                    "case_id": r[0],
                    "title": r[1],
                    "status": r[2],
                    "severity": r[3],
                    "created_at": r[4],
                    "updated_at": r[5],
                    "assigned_to": r[6]
                })
            
            cur.execute("SELECT COUNT(*) FROM cases WHERE tenant_id = %s", (auth.tenant_id,))
            total = cur.fetchone()[0]
            
            return {"total": total, "cases": cases}
    finally:
        conn.close()

@app.get("/cases/{case_id}")
def get_case(case_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title, description, severity, status, created_by, assigned_to, created_at, updated_at, closed_at FROM cases WHERE tenant_id = %s AND case_id = %s",
                (auth.tenant_id, case_id)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Case not found")
            
            return {
                "case_id": case_id,
                "title": row[0],
                "description": row[1],
                "severity": row[2],
                "status": row[3],
                "created_by": row[4],
                "assigned_to": row[5],
                "created_at": row[6],
                "updated_at": row[7],
                "closed_at": row[8]
            }
    finally:
        conn.close()

@app.get("/cases/{case_id}/timeline")
def get_case_timeline(case_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    conn = get_db_conn()
    timeline = []
    try:
        with conn.cursor() as cur:
            # Verify case exists
            cur.execute("SELECT 1 FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Case not found")

            # Get Tasks
            cur.execute("SELECT task_id, title, status, created_by, created_at FROM case_tasks WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            for r in cur.fetchall():
                timeline.append({"type": "task", "id": r[0], "title": r[1], "status": r[2], "user": r[3], "ts": r[4]})
            
            # Get Notes
            cur.execute("SELECT note_id, body, created_by, created_at FROM case_notes WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            for r in cur.fetchall():
                timeline.append({"type": "note", "id": r[0], "body": r[1], "user": r[2], "ts": r[3]})
                
            # Get Links
            cur.execute("SELECT original_event_id, linked_by, linked_at, link_reason FROM case_alert_links WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            for r in cur.fetchall():
                timeline.append({"type": "link", "alert_id": r[0], "user": r[1], "ts": r[2], "reason": r[3]})
                
    finally:
        conn.close()
    
    timeline.sort(key=lambda x: x['ts'], reverse=True)
    return {"case_id": case_id, "timeline": timeline}
