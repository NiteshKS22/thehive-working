import time
import uuid
import json
import logging
import sys
import os
import socket
import psycopg2
import hashlib
import itertools
from fastapi import FastAPI, HTTPException, Response, status, Depends, Body, Query, Request
from opensearchpy import OpenSearch
from typing import Dict, Any, Optional, List
import requests

# Robust common library discovery (handles local dev and Docker context)
_base_dir = os.path.dirname(__file__)
_paths_to_check = [
    os.path.abspath(os.path.join(_base_dir, '../../')), # Local dev (parent of common)
    os.path.abspath(os.path.join(_base_dir, '../')),     # Docker (parent of common)
]
for _p in _paths_to_check:
    if os.path.exists(os.path.join(_p, 'common')):
        sys.path.append(_p)
        break

from common.auth.middleware import get_auth_context, AuthContext, validate_auth_config, require_permission
from common.auth.rbac import PERM_ALERT_READ, PERM_CASE_READ, PERM_CASE_WRITE, PERM_RULE_SIMULATE, PERM_GRAPH_READ
from common.observability.metrics import MetricsMiddleware, get_metrics_response
from common.observability.health import global_health_registry

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("query-service")

app = FastAPI(title="NeuralVyuha Query Service")

app.add_middleware(MetricsMiddleware, service_name="nv-query")

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
PG_DB = os.getenv("POSTGRES_DB", "nv_vault")
PG_USER = os.getenv("POSTGRES_USER", "nv_user")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "nv_pass")

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

@app.get("/v1/user/current")
def get_current_user(auth: AuthContext = Depends(get_auth_context)):
    return {
        "login": auth.user_id if auth.user_id != "dev-user" else "admin@neuralvyuha.local",
        "name": "Administrator",
        "organisation": "admin",
        "tenant_id": auth.tenant_id,
        "roles": auth.roles,
        "permissions": list(auth.permissions),
        "token": auth.token
    }

from pydantic import BaseModel
import jwt

class LoginRequest(BaseModel):
    user: str
    password: str
    code: Optional[str] = None

@app.post("/login")
def login(req: LoginRequest):
    # Enterprise Dev Mock
    if req.user != "admin" or req.password != "admin":
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    secret = os.getenv("JWT_SECRET_KEY", "prod-secret-change-me")
    payload = {
        "sub": "admin@neuralvyuha.local",
        "tenant_id": "tenant-001",
        "roles": ["SYSTEM_ADMIN"],
        "exp": int(time.time()) + 3600
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return {"status": "success", "token": token}

@app.get("/status")
def get_status():
    """Return real-time health status of all platform services."""

    def probe_tcp(host, port, timeout=2):
        """Return 'UP' if TCP connection succeeds within timeout, else 'DOWN'."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return "UP"
        except Exception:
            return "DOWN"

    def probe_opensearch():
        try:
            ok = os_client.ping()
            return "UP" if ok else "DOWN"
        except Exception:
            return "DOWN"

    def probe_postgres():
        try:
            conn = get_db_conn()
            conn.close()
            return "UP"
        except Exception:
            return "DOWN"

    def probe_minio():
        minio_host = os.getenv("MINIO_HOST", "minio")
        minio_port = int(os.getenv("MINIO_PORT", 9000))
        return probe_tcp(minio_host, minio_port)

    def probe_redis():
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        return probe_tcp(redis_host, redis_port)

    def probe_redpanda():
        redpanda_host = os.getenv("REDPANDA_HOST", "redpanda")
        redpanda_port = int(os.getenv("REDPANDA_PORT", 9092))
        return probe_tcp(redpanda_host, redpanda_port)

    services = {
        "nv-query":   "UP",  # This service is running (we are responding)
        "opensearch": probe_opensearch(),
        "postgres":   probe_postgres(),
        "minio":      probe_minio(),
        "redis":      probe_redis(),
        "redpanda":   probe_redpanda(),
    }

    return {
        "version": "4.1.24-NV-ZENITH",
        "versions": {
            "TheHive": "4.1.24-NV-ZENITH"
        },
        "services": services,
        "connectors": {
            "cortex": { "enabled": True, "status": "OK", "servers": [] },
            "misp":   { "enabled": True, "status": "OK", "servers": [] }
        },
        "config": {
            "ssoAutoLogin": False
        }
    }

# ── Legacy TheHive v4 Compatibility Stub ────────────────────────────────────
# The original TheHive Angular frontend sends streaming queries to /v0/query.
# We intercept them and return sensible empty responses so the UI stays quiet.
from fastapi import Request as FARequest

_EMPTY_RESPONSES = {
    "caseTemplates":       [],
    "getOrganisation":     {"name": "admin", "description": "NeuralVyuha Org"},
    "countCases":          {"count": 0},
    "countAlerts":         {"count": 0},
    "customFields":        [],
    "taxonomies":          [],
    "tags":                [],
    "users":               [],
    "dashboards":          [],
    "observableTypes":     [],
    "listOrganisation":    [],
    "getUser":             {"login": "admin", "name": "Administrator"},
}

@app.post("/v0/query")
async def legacy_query_stub(request: FARequest):
    """
    Silent compatibility shim for TheHive v4 streaming query API.
    Inspects the _name chain and returns empty but valid data so the legacy
    Angular code doesn't throw unhandled-rejection errors.
    """
    try:
        body = await request.json()
        query_chain = body.get("query", [])
        # Last operation in the chain determines the return type
        result = []
        for step in reversed(query_chain):
            name = step.get("_name", "")
            if name in _EMPTY_RESPONSES:
                result = _EMPTY_RESPONSES[name]
                break
    except Exception:
        result = []
    return result


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
    status: Optional[str] = None,
    severity: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
    auth: AuthContext = Depends(require_permission(PERM_CASE_READ))
):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            query = "SELECT case_id, title, status, severity, created_at, updated_at, assigned_to, flag, closed_at, resolution_status, impact_status, summary FROM cases WHERE tenant_id = %s"
            params = [auth.tenant_id]
            
            # Visibility Filtering
            if "SYSTEM_ADMIN" not in auth.roles:
                query += " AND (visibility = 'ORGANIZATION' OR created_by = %s OR assigned_to = %s OR %s = ANY(permitted_users))"
                params.extend([auth.user_id, auth.user_id, auth.user_id])
            
            if status:
                status = status.upper()
                query += " AND status = %s"
                params.append(status)
            if severity:
                query += " AND severity = %s"
                params.append(severity)
            
            # Count Total (with visibility rules applied)
            count_query = query.replace("SELECT case_id, title, status, severity, created_at, updated_at, assigned_to, flag, closed_at, resolution_status, impact_status, summary", "SELECT COUNT(*)", 1)
            cur.execute(count_query, tuple(params))
            total = cur.fetchone()[0]

            query += " ORDER BY updated_at DESC LIMIT %s OFFSET %s"
            params.append(limit)
            params.append(offset)
            
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            
            cases = []
            for r in rows:
                cases.append({
                    "case_id": r[0],
                    "_id": r[0],
                    "id": r[0],
                    "title": r[1],
                    "status": r[2],
                    "severity": r[3],
                    "created_at": r[4],
                    "updated_at": r[5],
                    "assigned_to": r[6],
                    "flag": r[7] or False,
                    "closed_at": r[8],
                    "resolution_status": r[9],
                    "impact_status": r[10],
                    "summary": r[11]
                })
            
            return {"total": total, "cases": cases}
    finally:
        conn.close()

@app.get("/cases/{case_id}")
def get_case(case_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title, description, severity, status, visibility, permitted_users, created_by, assigned_to, created_at, updated_at, closed_at, flag, resolution_status, impact_status, summary, custom_fields FROM cases WHERE tenant_id = %s AND case_id = %s",
                (auth.tenant_id, case_id)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Case not found")
            
            visibility = row[4]
            permitted_users = row[5] or []
            created_by = row[6]
            assigned_to = row[7]

            # Visibility Check for Single Read
            if visibility == 'PRIVATE' and "SYSTEM_ADMIN" not in auth.roles:
                 if auth.user_id not in permitted_users and auth.user_id != created_by and auth.user_id != assigned_to:
                     raise HTTPException(status_code=403, detail="Access denied: Private Case")

            # Transform dict custom_fields back to array of objects for the UI
            custom_fields_dict = row[15] or {}
            custom_fields_arr = []
            for ref, val in custom_fields_dict.items():
                # Derive schema mapping back to UI object
                cf_type = list(val.keys())[0] if val and isinstance(val, dict) else "string"
                custom_fields_arr.append({
                    "name": ref,
                    "reference": ref,
                    "type": cf_type,
                    "value": val
                })

            return {
                "case_id": case_id,
                "_id": case_id,
                "id": case_id,
                "title": row[0],
                "description": row[1],
                "severity": row[2],
                "status": row[3],
                "visibility": visibility,
                "permitted_users": permitted_users,
                "created_by": created_by,
                "assigned_to": assigned_to,
                "created_at": row[8],
                "updated_at": row[9],
                "closed_at": row[10],
                "flag": row[11] or False,
                "resolution_status": row[12],
                "impact_status": row[13],
                "summary": row[14],
                "customFields": custom_fields_arr
            }
    finally:
        conn.close()

@app.get("/case/{case_id}/links")
def get_case_links(case_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    conn = get_db_conn()
    links = []
    try:
        with conn.cursor() as cur:
            # First, check case access
            cur.execute("SELECT visibility, permitted_users, created_by, assigned_to FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            c_row = cur.fetchone()
            if not c_row:
                raise HTTPException(status_code=404, detail="Case not found")
            
            visibility, permitted_users, created_by, assigned_to = c_row
            if visibility == 'PRIVATE' and "SYSTEM_ADMIN" not in auth.roles:
                 if auth.user_id not in (permitted_users or []) and auth.user_id != created_by and auth.user_id != assigned_to:
                     raise HTTPException(status_code=403, detail="Access denied: Private Case")

            cur.execute(
                """
                SELECT l.target_case_id, c.title, c.status, l.linked_by, l.linked_at 
                FROM case_links l
                JOIN cases c ON l.tenant_id = c.tenant_id AND l.target_case_id = c.case_id
                WHERE l.tenant_id = %s AND l.case_id = %s
                """,
                (auth.tenant_id, case_id)
            )
            for r in cur.fetchall():
                links.append({
                    "caseId": r[0],
                    "_id": r[0],
                    "target_case_id": r[0],
                    "title": r[1] or "Unknown Case",
                    "status": r[2],
                    "linked_by": r[3],
                    "linked_at": r[4],
                    "linkedWith": [] # Emulate zero shared observables strictly for UI array validation
                })
    finally:
        conn.close()
    return links

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
                
            # Get Links (Observables)
            cur.execute("SELECT original_event_id, linked_by, linked_at, link_reason FROM case_alert_links WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            for r in cur.fetchall():
                timeline.append({"type": "link", "alert_id": r[0], "user": r[1], "ts": r[2], "reason": r[3]})
                
    finally:
        conn.close()
    
    timeline.sort(key=lambda x: x['ts'], reverse=True)
    return {"case_id": case_id, "timeline": timeline}

# ── Tasks Read Endpoints ────────────────────────────────────────────────────────
@app.get("/case/{case_id}/task")
def list_case_tasks(case_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Case not found")
            cur.execute(
                "SELECT task_id, title, status, created_by, assigned_to, created_at, updated_at FROM case_tasks WHERE tenant_id = %s AND case_id = %s ORDER BY created_at ASC",
                (auth.tenant_id, case_id)
            )
            tasks = []
            for r in cur.fetchall():
                status = "Waiting" # Default for OPEN
                # If we want to distinguish InProgress, we'd need another field or logic.
                # For now, let's treat OPEN as Waiting so the Start button shows.
                tasks.append({
                    "_id": r[0], "id": r[0], "task_id": r[0],
                    "title": r[1], "status": status,
                    "createdBy": r[3], "assignee": r[4], "owner": r[4],
                    "startDate": r[5], "created_at": r[5], "updated_at": r[6],
                    "group": "default", "flag": False,
                    "extraData": {"shareCount": 0, "actionRequired": False}
                })
            return tasks
    finally:
        conn.close()

@app.get("/tasks/{task_id}")
def get_single_task(task_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT task_id, case_id, title, status, created_by, assigned_to, created_at, updated_at FROM case_tasks WHERE tenant_id = %s AND task_id = %s",
                (auth.tenant_id, task_id)
            )
            r = cur.fetchone()
            if not r:
                raise HTTPException(status_code=404, detail="Task not found")
            return {
                "_id": r[0], "id": r[0], "task_id": r[0], "case_id": r[1],
                "title": r[2], "status": r[3],
                "createdBy": r[4], "assignee": r[5], "owner": r[5],
                "startDate": r[6], "created_at": r[6], "updated_at": r[7],
                "group": "default", "flag": False,
                "extraData": {"shareCount": 0, "actionRequired": False}
            }
    finally:
        conn.close()

@app.get("/tasks/{task_id}/logs")
def get_task_logs(task_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT log_id, body, created_by, created_at FROM case_task_logs WHERE tenant_id = %s AND task_id = %s ORDER BY created_at DESC",
                (auth.tenant_id, task_id)
            )
            return [{"_id": r[0], "id": r[0], "message": r[1], "createdBy": r[2], "createdAt": r[3], "startDate": r[3]} for r in cur.fetchall()]
    finally:
        conn.close()

# ── Pages Proxy (direct Postgres) ───────────────────────────────────────────────
@app.get("/case/{case_id}/page")
def get_case_pages(case_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT page_id, title, content, created_by, created_at FROM case_pages WHERE tenant_id = %s AND case_id = %s ORDER BY created_at ASC",
                (auth.tenant_id, case_id)
            )
            return [{"_id": r[0], "id": r[0], "title": r[1], "content": r[2], "createdBy": r[3], "createdAt": r[4]} for r in cur.fetchall()]
    finally:
        conn.close()

# ── Observables (new table, direct Postgres) ────────────────────────────────────
@app.get("/case/{case_id}/observable")
def list_observables(case_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT observable_id, data_type, data, message, tlp, ioc, sighted, tags, created_by, created_at FROM case_observables WHERE tenant_id = %s AND case_id = %s ORDER BY created_at DESC",
                (auth.tenant_id, case_id)
            )
            return [{"_id": r[0], "id": r[0], "dataType": r[1], "data": r[2], "message": r[3], "tlp": r[4] or 2, "ioc": r[5] or False, "sighted": r[6] or False, "tags": r[7] or [], "createdBy": r[8], "createdAt": r[9], "startDate": r[9], "reports": {}} for r in cur.fetchall()]
    finally:
        conn.close()

# ── TTPs (new table, direct Postgres) ───────────────────────────────────────────
@app.get("/case/{case_id}/ttp")
def list_ttps(case_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ttp_id, tactic, technique_id, technique_name, created_by, created_at FROM case_ttps WHERE tenant_id = %s AND case_id = %s ORDER BY tactic, technique_id",
                (auth.tenant_id, case_id)
            )
            return [{"_id": r[0], "id": r[0], "tactic": r[1], "techniqueId": r[2], "techniqueName": r[3], "createdBy": r[4], "createdAt": r[5]} for r in cur.fetchall()]
    finally:
        conn.close()


# E3 Legacy Mapping for UI compatibility
@app.get("/api/case/{case_id}/links")
def legacy_get_case_links(case_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    return get_case_links(case_id, auth)


# ─── E8.1 Visual Vyuha — Graph Traversal API ──────────────────────────────────
#
# GET /graph/case/{case_id}
#
# Builds a node-link graph seeded from one Case:
#   • Collects every observable linked to the case.
#   • Finds all SAME-TENANT cases that share those observables.
#   • Cross-tenant hits are anonymized ("ANON" node, no IDs exposed).
#   • Hard cap of MAX_GRAPH_NODES to protect canvas performance.
#
# Response schema:
#   { nodes: [{id, label, node_type, tenant_id}], edges: [{source, target, label, observable}],
#     truncated: bool }
#
# Node types: "case" | "ip" | "file" | "user" | "hash" | "domain" | "cross_tenant"


@app.get("/observable/type")
def list_observable_types(auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    """Return common observable types for the legacy UI."""
    types = ["ip", "domain", "url", "hash", "user", "other", "file", "fqdn", "hostname", "mail", "mail_subject", "registry", "regexp", "filepath"]
    return [{"name": t, "label": t.capitalize()} for t in types]

@app.get("/api/observable/type")
def list_observable_types_legacy(auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    return list_observable_types(auth)

@app.get("/v1/describe/_all")
@app.get("/v0/describe/_all")
@app.get("/api/v1/describe/_all")
@app.get("/api/v0/describe/_all")
async def legacy_describe_all(auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    """Stub for legacy field description API."""
    return {
        "case": {"attributes": {}},
        "task": {"attributes": {}},
        "observable": {"attributes": {}},
        "ttp": {"attributes": {}},
        "page": {"attributes": {}},
        "procedure": {"attributes": {}},
        "observableTypes": [
            {"name": "ip", "label": "IP Address"},
            {"name": "domain", "label": "Domain"},
            {"name": "url", "label": "URL"},
            {"name": "hash", "label": "Hash"},
            {"name": "user", "label": "User"},
            {"name": "other", "label": "Other"}
        ],
        "customFields": []
    }

@app.post("/v1/describe/_all")
@app.post("/v0/describe/_all")
@app.post("/api/v1/describe/_all")
@app.post("/api/v0/describe/_all")
async def legacy_describe_all_post(auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    return {
        "case": {"attributes": {}},
        "task": {"attributes": {}},
        "observable": {"attributes": {}},
        "ttp": {"attributes": {}},
        "page": {"attributes": {}},
        "observableTypes": [
            {"name": "ip", "label": "IP Address"},
            {"name": "domain", "label": "Domain"},
            {"name": "url", "label": "URL"},
            {"name": "hash", "label": "Hash"},
            {"name": "user", "label": "User"},
            {"name": "other", "label": "Other"}
        ],
        "customFields": []
    }

MAX_GRAPH_NODES = 500


def _get_case_observables(cur, tenant_id: str, case_id: str):
    """Returns [(observable_value, observable_type)] linked to the case."""
    observables = []

    # Pull from case_alert_links → observable info stored in linked alerts (OpenSearch)
    cur.execute(
        "SELECT original_event_id FROM case_alert_links WHERE tenant_id = %s AND case_id = %s",
        (tenant_id, case_id)
    )
    alert_ids = [r[0] for r in cur.fetchall()]
    return alert_ids  # We'll resolve observables from alert payloads via OpenSearch


def _get_artifact_hashes(cur, tenant_id: str, case_id: str):
    """Returns [(sha256, filename)] for artifacts attached to the case."""
    try:
        cur.execute(
            "SELECT sha256, filename FROM artifacts WHERE tenant_id = %s AND case_id = %s",
            (tenant_id, case_id)
        )
        return cur.fetchall()
    except Exception:
        return []


def _resolve_alert_observables(alert_ids: list, tenant_id: str) -> list:
    """Fetch observable fields from OpenSearch alert docs for graph construction."""
    if not alert_ids:
        return []
    try:
        resp = os_client.search(
            body={
                "query": {"ids": {"values": alert_ids}},
                "size": len(alert_ids),
                "_source": ["tenant_id", "src_ip", "dst_ip", "file_hash", "username", "domain"]
            },
            index=INDEX_ALERTS
        )
        observables = []
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            if src.get("tenant_id") != tenant_id:
                continue  # Defence-in-depth tenant check
            if src.get("src_ip"):
                observables.append({"value": src["src_ip"], "type": "ip"})
            if src.get("dst_ip"):
                observables.append({"value": src["dst_ip"], "type": "ip"})
            if src.get("file_hash"):
                observables.append({"value": src["file_hash"], "type": "hash"})
            if src.get("username"):
                observables.append({"value": src["username"], "type": "user"})
            if src.get("domain"):
                observables.append({"value": src["domain"], "type": "domain"})
        return observables
    except Exception as e:
        logger.warning(f"graph: failed to resolve alert observables: {e}")
        return []


def _find_cases_sharing_observable(cur, own_tenant_id: str, obs_value: str, obs_type: str, exclude_case_id: str) -> list:
    """
    Find cases that share an observable (by IP/hash/user/domain).
    Returns list of dicts with {case_id, tenant_id, title}.
    Cross-tenant cases have title/case_id anonymized.
    """
    # Map observable type to field in alerts index (we'll do this via OpenSearch)
    field_map = {"ip": ["src_ip", "dst_ip"], "hash": ["file_hash"], "user": ["username"], "domain": ["domain"]}
    fields = field_map.get(obs_type, [])
    if not fields:
        return []

    # Build OS query: match observable in any relevant field
    should_clauses = [{"term": {f: obs_value}} for f in fields]
    try:
        resp = os_client.search(
            body={
                "query": {"bool": {"should": should_clauses, "minimum_should_match": 1}},
                "size": 100,
                "_source": ["tenant_id", "case_id"]
            },
            index=INDEX_ALERTS
        )
    except Exception as e:
        logger.warning(f"graph: observable search failed: {e}")
        return []

    results = []
    seen_cases = set()
    for hit in resp["hits"]["hits"]:
        src = hit["_source"]
        c_id = src.get("case_id")
        if not c_id or c_id == exclude_case_id or c_id in seen_cases:
            continue
        seen_cases.add(c_id)
        t_id = src.get("tenant_id", "")

        if t_id == own_tenant_id:
            # Fetch case title from Postgres
            try:
                cur.execute("SELECT title FROM cases WHERE tenant_id = %s AND case_id = %s", (t_id, c_id))
                row = cur.fetchone()
                title = row[0] if row else c_id
            except Exception:
                title = c_id
            results.append({"case_id": c_id, "tenant_id": t_id, "title": title, "cross_tenant": False})
        else:
            # TENANT_PRIVACY: anonymize cross-tenant hit — no IDs, no names
            results.append({
                "case_id": f"ANON_{hashlib.sha256(c_id.encode()).hexdigest()[:8]}",
                "tenant_id": "REDACTED",
                "title": "Seen in another tenant",
                "cross_tenant": True
            })
    return results


@app.get("/graph/case/{case_id}")
def get_case_graph(
    case_id: str,
    auth: AuthContext = Depends(require_permission(PERM_GRAPH_READ))
):
    """
    Visual Vyuha Graph API — returns a node-link graph seeded from a Case.

    Response: { nodes: [...], edges: [...], truncated: bool }
    Node types: case | ip | file | user | hash | domain | cross_tenant
    Node colours are assigned by the UI (Red=case, Blue=ip/domain, Green=file/hash, Yellow=user).
    """
    conn = get_db_conn()
    nodes: dict = {}   # node_id -> node dict
    edges: list = []
    truncated = False

    try:
        with conn.cursor() as cur:
            # 1. Verify seed case exists and belongs to tenant
            cur.execute(
                "SELECT title, severity, status FROM cases WHERE tenant_id = %s AND case_id = %s",
                (auth.tenant_id, case_id)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Case not found")

            seed_title, seed_severity, seed_status = row[0], row[1], row[2]

            # Add seed case node
            nodes[case_id] = {
                "id": case_id,
                "label": seed_title,
                "node_type": "case",
                "severity": seed_severity,
                "status": seed_status,
                "tenant_id": auth.tenant_id
            }

            # 2. Collect linked alert IDs
            alert_ids = _get_case_observables(cur, auth.tenant_id, case_id)

            # 3. Resolve observables from alert docs
            observables = _resolve_alert_observables(alert_ids, auth.tenant_id)

            # 4. Add artifact hashes as observables
            artifact_hashes = _get_artifact_hashes(cur, auth.tenant_id, case_id)
            for (sha256, filename) in artifact_hashes:
                observables.append({"value": sha256, "type": "hash", "label": filename or sha256[:16]})

            # 5. For each observable: create observable node + find sibling cases
            seen_edges = set()

            for obs in observables:
                obs_value = obs["value"]
                obs_type = obs["type"]
                obs_label = obs.get("label", obs_value)
                obs_node_id = f"{obs_type}:{obs_value}"

                if len(nodes) >= MAX_GRAPH_NODES:
                    truncated = True
                    break

                # Add observable node if needed
                if obs_node_id not in nodes:
                    nodes[obs_node_id] = {
                        "id": obs_node_id,
                        "label": obs_label,
                        "node_type": obs_type,
                        "tenant_id": auth.tenant_id
                    }

                # Edge: seed case → observable
                edge_key = f"{case_id}|{obs_node_id}"
                if edge_key not in seen_edges:
                    edges.append({
                        "source": case_id,
                        "target": obs_node_id,
                        "label": "has_observable",
                        "observable": obs_value
                    })
                    seen_edges.add(edge_key)

                # 6. Find sibling cases sharing this observable
                sibling_cases = _find_cases_sharing_observable(
                    cur, auth.tenant_id, obs_value, obs_type, case_id
                )

                for sibling in sibling_cases:
                    sibling_id = sibling["case_id"]

                    if len(nodes) >= MAX_GRAPH_NODES:
                        truncated = True
                        break

                    if sibling_id not in nodes:
                        node_type = "cross_tenant" if sibling["cross_tenant"] else "case"
                        nodes[sibling_id] = {
                            "id": sibling_id,
                            "label": sibling["title"],
                            "node_type": node_type,
                            "tenant_id": sibling["tenant_id"]
                        }

                    # Edge: sibling case → observable (or direct sibling→seed edge)
                    sibling_obs_key = f"{sibling_id}|{obs_node_id}"
                    if sibling_obs_key not in seen_edges:
                        edges.append({
                            "source": sibling_id,
                            "target": obs_node_id,
                            "label": "shares_observable",
                            "observable": obs_value
                        })
                        seen_edges.add(sibling_obs_key)

    finally:
        conn.close()

    logger.info(
        f"graph: case={case_id} tenant={auth.tenant_id} "
        f"nodes={len(nodes)} edges={len(edges)} truncated={truncated}"
    )

    return {
        "seed_case_id": case_id,
        "nodes": list(nodes.values()),
        "edges": edges,
        "truncated": truncated,
        "node_count": len(nodes),
        "edge_count": len(edges)
    }

# ── Default Legacy Query Fallback ──────────────────────────────────────────────

# ── Phase 4 Proxy Routes for Case Management ────────────────────────────────────
NV_CASE_ENGINE_URL = os.getenv("NV_CASE_ENGINE_URL", "http://nv-case-engine:8000")

def _forward_request(method, path, request: Request, auth: AuthContext, json_body=None):
    headers = {
        "Authorization": request.headers.get("Authorization", ""),
        "X-User-ID": auth.user_id,
        "X-Tenant-ID": auth.tenant_id,
    }
    # Forward Idempotency-Key if present
    idem_key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
    if idem_key:
        headers["Idempotency-Key"] = idem_key
    else:
        import uuid
        headers["Idempotency-Key"] = str(uuid.uuid4())
    url = f"{NV_CASE_ENGINE_URL}{path}"
    try:
        resp = requests.request(method, url, headers=headers, json=json_body)
        return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type", "application/json"))
    except Exception as e:
        logger.error(f"Error proxying to case engine: {e}")
        raise HTTPException(status_code=502, detail="Case Engine Gateway Error")

@app.post("/cases")
async def proxy_create_case(request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    body = await request.json()
    return _forward_request("POST", "/cases", request, auth, json_body=body)

@app.patch("/cases/{case_id}")
@app.patch("/case/{case_id}")
@app.patch("/api/case/{case_id}")
async def proxy_update_case(case_id: str, request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    body = await request.json()
    status_val = body.get("status")
    if status_val:
        if status_val.lower() == "resolved":
            body["status"] = "CLOSED"
        elif status_val.lower() in ["inprogress", "waiting"]:
            body["status"] = "OPEN"
    
    # Check if we have anything to update for a legacy UI patch 
    if not body:
        return {}

    return _forward_request("PATCH", f"/cases/{case_id}", request, auth, json_body=body)

@app.post("/cases/{case_id}/links")
async def proxy_link_case(case_id: str, request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    body = await request.json()
    return _forward_request("POST", f"/cases/{case_id}/links", request, auth, json_body=body)

@app.post("/case/{case_id}/task")
async def proxy_create_task(case_id: str, request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    body = await request.json()
    return _forward_request("POST", f"/case/{case_id}/task", request, auth, json_body=body)

@app.patch("/case/{case_id}/task/{task_id}")
async def proxy_update_task(case_id: str, task_id: str, request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    body = await request.json()
    return _forward_request("PATCH", f"/case/{case_id}/task/{task_id}", request, auth, json_body=body)

@app.post("/case/task/{task_id}/log")
async def proxy_create_task_log(task_id: str, request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    body = await request.json()
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT case_id FROM case_tasks WHERE tenant_id = %s AND task_id = %s", (auth.tenant_id, task_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Task not found")
            case_id = str(row[0])
    finally:
        conn.close()
    return _forward_request("POST", f"/case/{case_id}/task/{task_id}/log", request, auth, json_body=body)

@app.post("/case/template")
async def proxy_create_template(request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    body = await request.json()
    return _forward_request("POST", "/templates", request, auth, json_body=body)

@app.get("/case/template")
async def proxy_list_templates(request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    resp = _forward_request("GET", "/templates", request, auth)
    # The legacy UI expects a raw array of templates
    if hasattr(resp, "body"):
        try:
            data = json.loads(resp.body)
            if "templates" in data:
                return data["templates"]
        except Exception:
            pass
    elif isinstance(resp, dict) and "templates" in resp:
        return resp["templates"]
    return resp

@app.get("/case/{case_id}/export")
async def proxy_export_case(case_id: str, request: Request, password: Optional[str] = None, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    url = f"/cases/{case_id}/export"
    if password:
        url += f"?password={password}"
    return _forward_request("GET", url, request, auth)

@app.delete("/cases/{case_id}")
async def proxy_delete_case(case_id: str, request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    return _forward_request("DELETE", f"/cases/{case_id}", request, auth)

@app.post("/cases/merge/{case_ids}")
async def proxy_merge_cases(case_ids: str, request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    # case_ids is a comma separated string from the UI
    ids_list = [c.strip() for c in case_ids.split(",") if c.strip()]
    body = {"case_ids": ids_list}
    return _forward_request("POST", "/cases/merge", request, auth, json_body=body)

@app.post("/case/import")
async def proxy_import_case(request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    body = await request.json()
    return _forward_request("POST", "/cases/import", request, auth, json_body=body)

@app.post("/case/{case_id}/page")
@app.post("/api/case/{case_id}/page")
async def proxy_create_case_page(case_id: str, request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    body = await request.json()
    return _forward_request("POST", f"/case/{case_id}/page", request, auth, json_body=body)

@app.get("/case/{case_id}/page")
@app.get("/api/case/{case_id}/page")
async def proxy_list_case_pages(case_id: str, request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    return _forward_request("GET", f"/case/{case_id}/page", request, auth)

@app.delete("/case/{case_id}/page/{page_id}")
@app.delete("/api/case/{case_id}/page/{page_id}")
async def proxy_delete_case_page(case_id: str, page_id: str, request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    return _forward_request("DELETE", f"/case/{case_id}/page/{page_id}", request, auth)

@app.post("/case/{case_id}/observable")
@app.post("/api/case/{case_id}/observable")
@app.post("/api/case/{case_id}/artifact")
async def proxy_create_observable(case_id: str, request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    body = await request.json()
    return _forward_request("POST", f"/case/{case_id}/observable", request, auth, json_body=body)

@app.post("/case/{case_id}/ttp")
@app.post("/api/case/{case_id}/ttp")
async def proxy_create_ttp(case_id: str, request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    body = await request.json()
    return _forward_request("POST", f"/case/{case_id}/ttp", request, auth, json_body=body)


# Legacy Case Rewrite Middleware removed to avoid interference with new singular route structure.



# ── Stub Endpoints for Unimplemented Legacy Features ─────────────────────────
@app.get("/flow")
async def legacy_flow(request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    """Return empty array for activity flow/timeline — not yet implemented."""
    return []

@app.get("/customField")
@app.get("/api/customField")
async def legacy_custom_fields(request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    """Return common Enterprise Custom Field Definitions."""
    return [
        {"name": "business-impact", "reference": "business-impact", "type": "string", "description": "Business Impact"},
        {"name": "affected-users", "reference": "affected-users", "type": "number", "description": "Number of affected internal users"},
        {"name": "is-ransomware", "reference": "is-ransomware", "type": "boolean", "description": "Is Ransomware involved?"},
        {"name": "department", "reference": "department", "type": "string", "description": "Affected Department"}
    ]

@app.post("/case/task/_search")
async def legacy_task_search(request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    """Return empty array for task search — not yet implemented."""
    return []

@app.post("/case/_search")
async def legacy_case_search(request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    """Return empty array for legacy case search."""
    return []

@app.post("/query")
@app.post("/api/v1/query")
@app.post("/api/v0/query")
@app.post("/v1/query")
@app.post("/v0/query")
async def legacy_v0_v1_query(request: Request, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    """
    Catch-all for legacy /api/v0/query and /api/v1/query.
    Now intercepts Case Metrics rollups and queries Postgres.
    """
    body = await request.json()
    # The UI payload is typically { "query": [{ "_name": "countTask", "caseId": "..." }] }
    if isinstance(body, dict) and "query" in body and isinstance(body["query"], list):
        queries = body["query"]
        if len(queries) > 0:
            query_def = queries[0]
            action = query_def.get("_name")
            case_id = query_def.get("caseId")
            
            if action in ["countTask", "countCaseObservable", "countRelatedAlert"] and case_id:
                conn = get_db_conn()
                try:
                    with conn.cursor() as cur:
                        if action == "countTask":
                            # Exclude 'Cancel' status.
                            cur.execute("SELECT COUNT(*) FROM case_tasks WHERE tenant_id = %s AND case_id = %s AND status != 'Cancel'", (auth.tenant_id, case_id))
                            count = cur.fetchone()[0]
                            return [count]
                        elif action == "countCaseObservable":
                            # Note: OpenSearch is the primary artifact store. Let's do a fast distinct on pg artifacts for now.
                            cur.execute("SELECT COUNT(*) FROM artifacts WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
                            count = cur.fetchone()[0]
                            return [count]
                        elif action == "countRelatedAlert":
                            cur.execute("SELECT COUNT(*) FROM case_alert_links WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
                            count = cur.fetchone()[0]
                            return [count]
                except Exception as e:
                    logger.error(f"Metrics count failed: {e}")
                    return [0]
                finally:
                    conn.close()

    return []
