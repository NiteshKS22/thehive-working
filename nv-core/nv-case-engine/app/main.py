import time
import uuid
import json
import logging
import sys
import os
import psycopg2
from fastapi import FastAPI, Header, HTTPException, Response, status, Depends
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Import Auth Middleware
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
from common.auth.rbac import PERM_CASE_READ, PERM_CASE_WRITE
from common.observability.metrics import MetricsMiddleware, get_metrics_response
from common.observability.health import global_health_registry
from common.config.secrets import get_secret

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("nv-case-engine")

app = FastAPI(title="NeuralVyuha Case Service")

# Observability
app.add_middleware(MetricsMiddleware, service_name="nv-case-engine")

@app.on_event("startup")
def startup_event():
    validate_auth_config()

    # Health Checks
    def check_kafka():
        return producer and producer.bootstrap_connected()

    global_health_registry.add_check("kafka", check_kafka)

    def check_db():
        try:
            conn = get_db_conn()
            conn.close()
            return True
        except:
            return False

    global_health_registry.add_check("db", check_db)

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:29092")

# DB Config
POSTGRES_HOST = get_secret("POSTGRES_HOST", "postgres")
POSTGRES_USER = get_secret("POSTGRES_USER", "hive")
POSTGRES_PASSWORD = get_secret("POSTGRES_PASSWORD", "hive")
POSTGRES_DB = get_secret("POSTGRES_DB", "thehive")

def get_db_conn():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

try:
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    logger.info("Kafka producer initialized")
except Exception as e:
    logger.error(f"Failed to initialize Kafka producer: {e}")
    producer = None

def emit_event(topic, event_type, payload, auth):
    if not producer:
        logger.warning(f"No producer, skipping event: {event_type}")
        return

    event = {
        "event_id": str(uuid.uuid4()),
        "type": event_type,
        "tenant_id": auth.tenant_id,
        "timestamp": int(time.time() * 1000),
        "schema_version": "1.0",
        "payload": payload
    }

    try:
        producer.send(topic, value=event)
        producer.flush()
    except Exception as e:
        logger.error(f"Failed to emit event: {e}")

# Models
class CreateCaseRequest(BaseModel):
    title: str
    description: Optional[str] = None
    severity: int = Field(default=2, ge=1, le=4)
    tlp: int = Field(default=2, ge=0, le=3)
    pap: int = Field(default=2, ge=0, le=3)
    assignee: Optional[str] = None
    visibility: str = Field(default="ORGANIZATION")
    permitted_users: Optional[list[str]] = None

class UpdateCaseRequest(BaseModel):
    model_config = ConfigDict(extra='allow')
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[int] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    visibility: Optional[str] = None
    permitted_users: Optional[list[str]] = None
    flag: Optional[bool] = None
    resolutionStatus: Optional[str] = None
    impactStatus: Optional[str] = None
    summary: Optional[str] = None

class MergeCasesRequest(BaseModel):
    case_ids: list[str]

class CreateTaskRequest(BaseModel):
    title: str
    assigned_to: Optional[str] = None

class CreateNoteRequest(BaseModel):
    body: str

class LinkAlertRequest(BaseModel):
    original_event_id: str
    link_reason: Optional[str] = None

class LinkCaseRequest(BaseModel):
    target_case_id: str

class UpdateTaskRequest(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None
    assigned_to: Optional[str] = None

class TemplateTaskRequest(BaseModel):
    title: str
    description: Optional[str] = None

class CreateTemplateRequest(BaseModel):
    name: str
    title_prefix: str
    severity: int = 2
    description: Optional[str] = None
    tasks: list[TemplateTaskRequest] = []

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

# T2: Idempotency Helper
def check_idempotency(cur, tenant_id, key):
    cur.execute(
        "SELECT response_json FROM idempotency_keys WHERE tenant_id = %s AND key_id = %s",
        (tenant_id, key)
    )
    row = cur.fetchone()
    if row:
        return json.loads(row[0])
    return None

def save_idempotency(cur, tenant_id, key, response):
    cur.execute(
        "INSERT INTO idempotency_keys (tenant_id, key_id, response_json, created_at) VALUES (%s, %s, %s, %s)",
        (tenant_id, key, json.dumps(response), int(time.time() * 1000))
    )

@app.post("/cases", status_code=201)
def create_case(
    req: CreateCaseRequest,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"), # Mandatory
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    case_id = str(uuid.uuid4())
    now = int(time.time() * 1000)

    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            # 1. Check Idempotency (T2)
            cached = check_idempotency(cur, auth.tenant_id, idempotency_key)
            if cached:
                response.status_code = 200 # OK, not Created
                return cached

            # 2. Create Case (with entity_version T3)
            cur.execute(
                """
                INSERT INTO cases (tenant_id, case_id, title, description, severity, status, visibility, permitted_users, created_by, assigned_to, created_at, updated_at, entity_version)
                VALUES (%s, %s, %s, %s, %s, 'OPEN', %s, %s, %s, %s, %s, %s, 1)
                """,
                (auth.tenant_id, case_id, req.title, req.description, req.severity, req.visibility, req.permitted_users, auth.user_id, req.assignee, now, now)
            )

            resp_body = {"case_id": case_id, "status": "created"}

            # 3. Save Idempotency
            save_idempotency(cur, auth.tenant_id, idempotency_key, resp_body)

        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        # Race condition on idempotency key?
        # Re-check or fail
        raise HTTPException(status_code=409, detail="Idempotency key conflict")
    except Exception as e:
        conn.rollback()
        logger.error(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        conn.close()

    emit_event("nv.cases.created.v1", "CaseCreated", {
        "case_id": case_id,
        "title": req.title,
        "created_by": auth.user_id,
        "version": 1
    }, auth)

    return resp_body

@app.patch("/cases/{case_id}")
def update_case(
    case_id: str,
    req: UpdateCaseRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    conn = get_db_conn()
    updated_at = int(time.time() * 1000)

    # Idempotency check for PATCH (optional but recommended for critical updates)
    if idempotency_key:
         with conn.cursor() as cur:
            cached = check_idempotency(cur, auth.tenant_id, idempotency_key)
            if cached:
                return cached

    fields = []
    params = []

    if req.title is not None:
        fields.append("title = %s")
        params.append(req.title)
    if req.description is not None:
        fields.append("description = %s")
        params.append(req.description)
    if req.severity is not None:
        fields.append("severity = %s")
        params.append(req.severity)
    if req.assigned_to is not None:
        fields.append("assigned_to = %s")
        params.append(req.assigned_to)
    if req.status is not None:
        fields.append("status = %s")
        params.append(req.status)
        if req.status == 'CLOSED':
            fields.append("closed_at = %s")
            params.append(updated_at)
        elif req.status == 'OPEN':
            fields.append("closed_at = NULL")
    if req.visibility is not None:
        fields.append("visibility = %s")
        params.append(req.visibility)
    if req.permitted_users is not None:
        fields.append("permitted_users = %s")
        params.append(req.permitted_users)
    if req.flag is not None:
        fields.append("flag = %s")
        params.append(req.flag)
    if req.resolutionStatus is not None:
        fields.append("resolution_status = %s")
        params.append(req.resolutionStatus)
    if req.impactStatus is not None:
        fields.append("impact_status = %s")
        params.append(req.impactStatus)
    if req.summary is not None:
        fields.append("summary = %s")
        params.append(req.summary)

    # Persist Dynamic Custom Fields
    custom_fields_updates = {}
    dumped_req = req.model_dump(exclude_unset=True)
    for k, v in dumped_req.items():
        if k.startswith("customFields."):
            ref = k.split(".", 1)[1]
            custom_fields_updates[ref] = v

    if custom_fields_updates:
        fields.append("custom_fields = COALESCE(custom_fields, '{}'::jsonb) || %s::jsonb")
        params.append(json.dumps(custom_fields_updates))

    if not fields:
        return {"status": "no_change"}

    fields.append("updated_at = %s")
    params.append(updated_at)

    # T3: Increment Version
    fields.append("entity_version = entity_version + 1")

    params.append(auth.tenant_id)
    params.append(case_id)

    resp_body = {"status": "updated"}

    try:
        with conn.cursor() as cur:
            sql = f"UPDATE cases SET {', '.join(fields)} WHERE tenant_id = %s AND case_id = %s RETURNING entity_version"
            cur.execute(sql, tuple(params))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Case not found")

            new_version = row[0]
            resp_body["version"] = new_version

            if idempotency_key:
                save_idempotency(cur, auth.tenant_id, idempotency_key, resp_body)

        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    emit_event("nv.cases.updated.v1", "CaseUpdated", {
        "case_id": case_id,
        "updates": req.model_dump(exclude_unset=True),
        "updated_by": auth.user_id,
        "version": new_version
    }, auth)

    if req.status == 'CLOSED':
         emit_event("nv.cases.closed.v1", "CaseClosed", {"case_id": case_id, "closed_by": auth.user_id}, auth)

    return resp_body

@app.delete("/cases/{case_id}")
def delete_case(case_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Case not found")
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    
    emit_event("nv.cases.deleted.v1", "CaseDeleted", {"case_id": case_id}, auth)
    return {"status": "deleted"}

@app.post("/cases/merge")
def merge_cases(req: MergeCasesRequest, auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))):
    # Stub for enterprise merge. Moving sub-entities requires complex domain logic.
    return {"status": "merged"}

@app.get("/cases/{case_id}/export")
def export_case(case_id: str, password: Optional[str] = None, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    import tempfile, zipfile
    from fastapi.responses import FileResponse
    # Enterprise Export Stub
    _, path = tempfile.mkstemp(suffix=".zip")
    with zipfile.ZipFile(path, 'w') as zipf:
        zipf.writestr('case_export.json', b'{"case_id": "' + case_id.encode() + b'", "status": "exported"}')
    return FileResponse(path, media_type='application/zip', filename=f"{case_id}_export.zip")

@app.post("/cases/{case_id}/links", status_code=201)
def link_case(
    case_id: str,
    req: LinkCaseRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    conn = get_db_conn()
    try:
        now = int(time.time() * 1000)
        with conn.cursor() as cur:
            # Check source case
            cur.execute("SELECT 1 FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Source case not found")
                
            # Check target case
            cur.execute("SELECT 1 FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, req.target_case_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Target case not found")
                
            # Perform Bidirectional Linking - A to B
            cur.execute(
                "INSERT INTO case_links (tenant_id, case_id, target_case_id, linked_by, linked_at) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (auth.tenant_id, case_id, req.target_case_id, auth.user_id, now)
            )
            # Perform Bidirectional Linking - B to A
            cur.execute(
                "INSERT INTO case_links (tenant_id, case_id, target_case_id, linked_by, linked_at) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (auth.tenant_id, req.target_case_id, case_id, auth.user_id, now)
            )
            
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
    emit_event("nv.cases.linked.v1", "CaseLinked", {
        "case_id": case_id,
        "target_case_id": req.target_case_id,
        "linked_by": auth.user_id
    }, auth)
    
    return {"status": "linked"}

@app.post("/case/{case_id}/task", status_code=201)
def create_task(
    case_id: str,
    req: CreateTaskRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    task_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO case_tasks (tenant_id, case_id, task_id, title, status, created_by, assigned_to, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 'OPEN', %s, %s, %s, %s)
                """,
                (auth.tenant_id, case_id, task_id, req.title, auth.user_id, req.assigned_to, now, now)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    emit_event("nv.cases.task.created.v1", "TaskCreated", {
        "case_id": case_id,
        "task_id": task_id,
        "title": req.title
    }, auth)
    return {"task_id": task_id, "status": "created"}

@app.patch("/case/{case_id}/task/{task_id}")
def update_task(
    case_id: str,
    task_id: str,
    req: UpdateTaskRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    fields = []
    params = []
    if req.status is not None:
        fields.append("status = %s")
        params.append(req.status)
    if req.title is not None:
        fields.append("title = %s")
        params.append(req.title)
    if req.assigned_to is not None:
        fields.append("assigned_to = %s")
        params.append(req.assigned_to)

    if not fields:
        return {"status": "no_change"}

    now = int(time.time() * 1000)
    fields.append("updated_at = %s")
    params.append(now)

    params.extend([auth.tenant_id, case_id, task_id])

    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            sql = f"UPDATE case_tasks SET {', '.join(fields)} WHERE tenant_id = %s AND case_id = %s AND task_id = %s"
            cur.execute(sql, tuple(params))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Task not found")
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    emit_event("nv.cases.task.updated.v1", "TaskUpdated", {
        "case_id": case_id,
        "task_id": task_id,
        "updates": req.model_dump(exclude_unset=True)
    }, auth)
    return {"status": "updated"}

@app.post("/case/{case_id}/task/{task_id}/log", status_code=201)
def create_task_log(
    case_id: str,
    task_id: str,
    req: CreateNoteRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    log_id = str(uuid.uuid4())
    now = int(time.time() * 1000)

    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO case_task_logs (tenant_id, case_id, task_id, log_id, body, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (auth.tenant_id, case_id, task_id, log_id, req.body, auth.user_id, now)
            )
        conn.commit()
    except psycopg2.errors.ForeignKeyViolation:
         conn.rollback()
         raise HTTPException(status_code=404, detail="Case or Task not found")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    emit_event("nv.cases.task.log.created.v1", "TaskLogCreated", {
        "case_id": case_id,
        "task_id": task_id,
        "log_id": log_id
    }, auth)
    return {"log_id": log_id, "status": "created"}

@app.get("/case/{case_id}/task")
def list_tasks(
    case_id: str,
    status: Optional[str] = None,
    auth: AuthContext = Depends(require_permission(PERM_CASE_READ))
):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            query = "SELECT task_id, title, status, created_by, assigned_to, created_at, updated_at FROM case_tasks WHERE tenant_id = %s AND case_id = %s"
            params = [auth.tenant_id, case_id]
            if status:
                query += " AND status = %s"
                params.append(status.upper())
            query += " ORDER BY created_at ASC"
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            tasks = []
            for r in rows:
                tasks.append({
                    "_id": r[0], "id": r[0], "task_id": r[0],
                    "title": r[1], "status": r[2],
                    "createdBy": r[3], "assignee": r[4], "owner": r[4],
                    "startDate": r[5], "created_at": r[5],
                    "updated_at": r[6],
                    "group": "default", "flag": False,
                    "extraData": {"shareCount": 0, "actionRequired": False}
                })
            return tasks
    finally:
        conn.close()

@app.get("/tasks/{task_id}")
def get_task(
    task_id: str,
    auth: AuthContext = Depends(require_permission(PERM_CASE_READ))
):
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
                "_id": r[0], "id": r[0], "task_id": r[0],
                "case_id": r[1], "title": r[2], "status": r[3],
                "createdBy": r[4], "assignee": r[5], "owner": r[5],
                "startDate": r[6], "created_at": r[6], "updated_at": r[7],
                "group": "default", "flag": False,
                "extraData": {"shareCount": 0, "actionRequired": False}
            }
    finally:
        conn.close()

@app.get("/case/{case_id}/task/{task_id}/log")
def list_task_logs(
    task_id: str,
    auth: AuthContext = Depends(require_permission(PERM_CASE_READ))
):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT log_id, body, created_by, created_at FROM case_task_logs WHERE tenant_id = %s AND task_id = %s ORDER BY created_at DESC",
                (auth.tenant_id, task_id)
            )
            rows = cur.fetchall()
            logs = []
            for r in rows:
                logs.append({
                    "_id": r[0], "id": r[0], "log_id": r[0],
                    "message": r[1], "createdBy": r[2], "createdAt": r[3],
                    "startDate": r[3]
                })
            return logs
    finally:
        conn.close()

@app.delete("/cases/{case_id}/tasks/{task_id}")
def delete_task(
    case_id: str,
    task_id: str,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM case_tasks WHERE tenant_id = %s AND case_id = %s AND task_id = %s",
                (auth.tenant_id, case_id, task_id)
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Task not found")
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    emit_event("nv.cases.task.deleted.v1", "TaskDeleted", {"case_id": case_id, "task_id": task_id}, auth)
    return {"status": "deleted"}

@app.post("/templates", status_code=201)
def create_template(
    req: CreateTemplateRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    template_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO case_templates (tenant_id, template_id, name, title_prefix, severity, description, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (auth.tenant_id, template_id, req.name, req.title_prefix, req.severity, req.description, auth.user_id, now)
            )

            for t_task in req.tasks:
                t_task_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO case_template_tasks (tenant_id, template_id, task_id, title, description)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (auth.tenant_id, template_id, t_task_id, t_task.title, t_task.description)
                )

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    return {"template_id": template_id, "status": "created"}

@app.get("/templates")
def list_templates(
    auth: AuthContext = Depends(require_permission(PERM_CASE_READ))
):
    conn = get_db_conn()
    templates = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT template_id, name, title_prefix, severity, description, created_by, created_at
                FROM case_templates WHERE tenant_id = %s
                ORDER BY name ASC
                """,
                (auth.tenant_id,)
            )
            for r in cur.fetchall():
                templates.append({
                    "id": r[0],
                    "_id": r[0],
                    "name": r[1],
                    "titlePrefix": r[2],
                    "severity": r[3],
                    "description": r[4],
                    "createdBy": r[5],
                    "createdAt": r[6]
                })

            # Fetch tasks for each template
            if templates:
                cur.execute(
                    "SELECT template_id, title, description FROM case_template_tasks WHERE tenant_id = %s",
                    (auth.tenant_id,)
                )
                tasks_map = {}
                for tr in cur.fetchall():
                    tid = tr[0]
                    if tid not in tasks_map:
                        tasks_map[tid] = []
                    tasks_map[tid].append({"title": tr[1], "description": tr[2]})

                for t in templates:
                    t["tasks"] = tasks_map.get(t["id"], [])

    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        conn.close()

    return templates

@app.get("/cases/{case_id}/export")
def export_case(
    case_id: str,
    password: Optional[str] = None,
    auth: AuthContext = Depends(require_permission(PERM_CASE_READ))
):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            # Get Case
            cur.execute(
                "SELECT title, description, severity, status, created_by, assigned_to, created_at, updated_at "
                "FROM cases WHERE tenant_id = %s AND case_id = %s",
                (auth.tenant_id, case_id)
            )
            c_row = cur.fetchone()
            if not c_row:
                raise HTTPException(status_code=404, detail="Case not found")

            case_data = {
                "id": case_id,
                "title": c_row[0],
                "description": c_row[1],
                "severity": c_row[2],
                "status": c_row[3],
                "createdBy": c_row[4],
                "assignedTo": c_row[5],
                "createdAt": c_row[6],
                "updatedAt": c_row[7],
                "tasks": [],
                "pages": []
            }

            # Get Tasks
            cur.execute(
                "SELECT task_id, title, status, created_by, assigned_to, created_at "
                "FROM case_tasks WHERE tenant_id = %s AND case_id = %s",
                (auth.tenant_id, case_id)
            )
            tasks = cur.fetchall()

            for t in tasks:
                t_id = t[0]
                task_data = {
                    "id": t_id,
                    "title": t[1],
                    "status": t[2],
                    "createdBy": t[3],
                    "assignedTo": t[4],
                    "createdAt": t[5],
                    "logs": []
                }

                # Get Task Logs
                cur.execute(
                     "SELECT log_id, body, created_by, created_at "
                     "FROM case_task_logs WHERE tenant_id = %s AND case_id = %s AND task_id = %s ORDER BY created_at ASC",
                     (auth.tenant_id, case_id, t_id)
                )
                logs = cur.fetchall()
                for l in logs:
                    task_data["logs"].append({
                        "id": l[0],
                        "body": l[1],
                        "createdBy": l[2],
                        "createdAt": l[3]
                    })
                
                case_data["tasks"].append(task_data)

            # Get Pages
            cur.execute(
                "SELECT page_id, title, content, created_by, created_at, updated_at "
                "FROM case_pages WHERE tenant_id = %s AND case_id = %s",
                (auth.tenant_id, case_id)
            )
            pages = cur.fetchall()
            for p in pages:
                case_data["pages"].append({
                    "id": p[0],
                    "title": p[1],
                    "content": p[2],
                    "createdBy": p[3],
                    "createdAt": p[4],
                    "updatedAt": p[5]
                })

    except HTTPException:
        raise
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))
    finally:
         conn.close()

    export_payload = {
         "version": "1.0",
         "exportedAt": int(time.time() * 1000),
         "exportedBy": auth.user_id,
         "case": case_data
    }
    case_json_str = json.dumps(export_payload, indent=2)

    if not password:
        return Response(content=case_json_str, media_type="application/json")

    import io
    import pyzipper
    
    zip_buffer = io.BytesIO()
    with pyzipper.AESZipFile(zip_buffer, 'w', compression=pyzipper.ZIP_LZMA, encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(password.encode('utf-8'))
        zf.writestr(f"case_{case_id}.json", case_json_str)
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=case_{case_id}.zip"}
    )

@app.post("/cases/import", status_code=201)
def import_case(
    import_data: Dict[str, Any],
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    case_data = import_data.get("case", import_data)
    conn = get_db_conn()
    try:
        new_case_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cases (tenant_id, case_id, title, description, severity, status, created_by, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (auth.tenant_id, new_case_id, case_data.get("title", "Imported Case"), case_data.get("description", ""), case_data.get("severity", 2),
                 case_data.get("status", "OPEN"), auth.user_id, now, now)
            )
            
            for t in case_data.get("tasks", []):
                new_task_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO case_tasks (tenant_id, case_id, task_id, title, status, created_by, assigned_to, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (auth.tenant_id, new_case_id, new_task_id, t.get("title", "Task"), t.get("status", "OPEN"), auth.user_id, t.get("assignedTo"), now, now)
                )
                
                for l in t.get("logs", []):
                    new_log_id = str(uuid.uuid4())
                    cur.execute(
                        "INSERT INTO case_task_logs (tenant_id, case_id, task_id, log_id, body, created_by, created_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (auth.tenant_id, new_case_id, new_task_id, new_log_id, l.get("body", ""), auth.user_id, now)
                    )
            
            for p in case_data.get("pages", []):
                new_page_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO case_pages (tenant_id, case_id, page_id, title, content, created_by, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (auth.tenant_id, new_case_id, new_page_id, p.get("title", "Page"), p.get("content", ""), auth.user_id, now, now)
                )
            conn.commit()
            
            emit_event("nv-cases-events", "nv.cases.imported.v1", {"case_id": new_case_id}, auth)

    except Exception as e:
        conn.rollback()
        logger.error(f"Error importing case: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        conn.close()

    return {"status": "success", "case_id": new_case_id}

@app.delete("/cases/{case_id}", status_code=204)
def delete_case(
    case_id: str,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Case not found")
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting case: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        conn.close()

    emit_event("nv.cases.deleted.v1", "CaseDeleted", {"case_id": case_id, "deleted_by": auth.user_id}, auth)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.post("/cases/merge", status_code=200)
def merge_cases(
    req: MergeCasesRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    if not req.case_ids or len(req.case_ids) < 2:
        raise HTTPException(status_code=400, detail="Must provide at least two case IDs to merge.")

    # Target case is the first one in the list
    target_case_id = req.case_ids[0]
    source_case_ids = req.case_ids[1:]
    
    conn = get_db_conn()
    now = int(time.time() * 1000)
    
    try:
        with conn.cursor() as cur:
            # Verify target exists
            cur.execute("SELECT 1 FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, target_case_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail=f"Target case {target_case_id} not found")

            for src_id in source_case_ids:
                # Append links to target case
                cur.execute(
                    "INSERT INTO case_links (tenant_id, case_id, target_case_id, linked_by, linked_at) "
                    "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (auth.tenant_id, target_case_id, src_id, auth.user_id, now)
                )

                # Close source cases
                cur.execute(
                    "UPDATE cases SET status = 'CLOSED', resolution_status = 'Duplicated', summary = %s, closed_at = %s, updated_at = %s, entity_version = entity_version + 1 "
                    "WHERE tenant_id = %s AND case_id = %s",
                    (f"Merged into {target_case_id}", now, now, auth.tenant_id, src_id)
                )

        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error merging cases: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        conn.close()

    emit_event("nv.cases.merged.v1", "CasesMerged", {
        "target_case_id": target_case_id,
        "source_case_ids": source_case_ids,
        "merged_by": auth.user_id
    }, auth)

    return {"status": "merged", "target_case_id": target_case_id}

# ── Phase 5.2 Case Pages ────────────────────────────────────────────────────────
class CreatePageRequest(BaseModel):
    title: str = Field(..., max_length=255)
    content: str

@app.post("/case/{case_id}/page", status_code=201)
def create_case_page(
    case_id: str,
    req: CreatePageRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    conn = get_db_conn()
    try:
        page_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        with conn.cursor() as cur:
            # Check case exists
            cur.execute("SELECT 1 FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Case not found")

            cur.execute(
                "INSERT INTO case_pages (tenant_id, case_id, page_id, title, content, created_by, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (auth.tenant_id, case_id, page_id, req.title, req.content, auth.user_id, now, now)
            )
            conn.commit()
            
            # Emit Event
            emit_event(
                topic="nv-cases-events",
                event_type="nv.cases.page.created.v1",
                payload={"case_id": case_id, "page_id": page_id, "title": req.title},
                auth=auth
            )
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating case page: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        conn.close()

    return {"id": page_id, "page_id": page_id, "title": req.title, "content": req.content, "createdAt": now, "createdBy": auth.user_id}

@app.get("/case/{case_id}/page")
def get_case_pages(
    case_id: str,
    auth: AuthContext = Depends(require_permission(PERM_CASE_READ))
):
    conn = get_db_conn()
    try:
        pages = []
        with conn.cursor() as cur:
            cur.execute(
                "SELECT page_id, title, content, created_by, created_at, updated_at "
                "FROM case_pages WHERE tenant_id = %s AND case_id = %s ORDER BY created_at ASC",
                (auth.tenant_id, case_id)
            )
            for r in cur.fetchall():
                pages.append({
                    "id": r[0],
                    "_id": r[0],
                    "title": r[1],
                    "content": r[2],
                    "createdBy": r[3],
                    "createdAt": r[4],
                    "updatedAt": r[5]
                })
    except Exception as e:
        logger.error(f"Error listing case pages: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        conn.close()

    return pages

@app.delete("/case/{case_id}/page/{page_id}", status_code=204)
def delete_case_page(
    case_id: str,
    page_id: str,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM case_pages WHERE tenant_id = %s AND case_id = %s AND page_id = %s",
                (auth.tenant_id, case_id, page_id)
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Page not found")
            conn.commit()
            
            # Emit Event
            emit_event(
                topic="nv-cases-events",
                event_type="nv.cases.page.deleted.v1",
                payload={"case_id": case_id, "page_id": page_id},
                auth=auth
            )
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting case page: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        conn.close()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# ── Phase 9: Observables ────────────────────────────────────────────────────────
class CreateObservableRequest(BaseModel):
    dataType: Optional[str] = None
    data: Optional[str] = None
    type: Optional[str] = None
    value: Optional[str] = None
    message: Optional[str] = None
    tlp: int = Field(default=2, ge=0, le=3)
    ioc: bool = False
    sighted: bool = False
    tags: list[str] = []

    def get_type(self) -> str:
        return self.type or self.dataType or "other"

    def get_value(self) -> str:
        return self.value or self.data or ""


class UpdateObservableRequest(BaseModel):
    message: Optional[str] = None
    tlp: Optional[int] = None
    ioc: Optional[bool] = None
    sighted: Optional[bool] = None
    tags: Optional[list[str]] = None

@app.post("/case/{case_id}/observable", status_code=201)
def create_observable(
    case_id: str,
    req: CreateObservableRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    obs_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Case not found")
            cur.execute(
                """INSERT INTO case_observables (tenant_id, case_id, observable_id, data_type, data, message, tlp, ioc, sighted, tags, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (auth.tenant_id, case_id, obs_id, req.get_type(), req.get_value(), req.message, req.tlp, req.ioc, req.sighted, req.tags, auth.user_id, now)
            )
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    emit_event("nv.cases.observable.created.v1", "ObservableCreated", {"case_id": case_id, "observable_id": obs_id}, auth)
    return {"observable_id": obs_id, "status": "created"}

@app.get("/case/{case_id}/observable")
def get_observables(
    case_id: str,
    auth: AuthContext = Depends(require_permission(PERM_CASE_READ))
):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT observable_id, data_type, data, message, tlp, ioc, sighted, tags, created_by, created_at FROM case_observables WHERE tenant_id = %s AND case_id = %s ORDER BY created_at DESC",
                (auth.tenant_id, case_id)
            )
            return [{"_id": r[0], "id": r[0], "dataType": r[1], "data": r[2], "message": r[3], "tlp": r[4], "ioc": r[5], "sighted": r[6], "tags": r[7] or [], "createdBy": r[8], "createdAt": r[9], "startDate": r[9], "reports": {}} for r in cur.fetchall()]
    finally:
        conn.close()

@app.patch("/case/{case_id}/observable/{obs_id}")
def update_observable(
    case_id: str,
    obs_id: str,
    req: UpdateObservableRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            updates, params = [], []
            if req.message is not None:
                updates.append("message = %s"); params.append(req.message)
            if req.tlp is not None:
                updates.append("tlp = %s"); params.append(req.tlp)
            if req.ioc is not None:
                updates.append("ioc = %s"); params.append(req.ioc)
            if req.sighted is not None:
                updates.append("sighted = %s"); params.append(req.sighted)
            if req.tags is not None:
                updates.append("tags = %s"); params.append(req.tags)
            if not updates:
                return {"status": "no_change"}
            params.extend([auth.tenant_id, case_id, obs_id])
            cur.execute(f"UPDATE case_observables SET {', '.join(updates)} WHERE tenant_id = %s AND case_id = %s AND observable_id = %s", tuple(params))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Observable not found")
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"status": "updated"}

@app.delete("/case/{case_id}/observable/{obs_id}")
def delete_observable(
    case_id: str,
    obs_id: str,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM case_observables WHERE tenant_id = %s AND case_id = %s AND observable_id = %s", (auth.tenant_id, case_id, obs_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Observable not found")
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    emit_event("nv.cases.observable.deleted.v1", "ObservableDeleted", {"case_id": case_id, "observable_id": obs_id}, auth)
    return {"status": "deleted"}

# ── Phase 9: TTPs (MITRE ATT&CK) ───────────────────────────────────────────────
class CreateTtpRequest(BaseModel):
    tactic: str
    techniqueId: str
    techniqueName: str

@app.post("/case/{case_id}/ttp", status_code=201)
def create_ttp(
    case_id: str,
    req: CreateTtpRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    ttp_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Case not found")
            cur.execute(
                """INSERT INTO case_ttps (tenant_id, case_id, ttp_id, tactic, technique_id, technique_name, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (auth.tenant_id, case_id, ttp_id, req.tactic, req.techniqueId, req.techniqueName, auth.user_id, now)
            )
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    emit_event("nv.cases.ttp.created.v1", "TTPCreated", {"case_id": case_id, "ttp_id": ttp_id}, auth)
    return {"ttp_id": ttp_id, "status": "created"}

@app.get("/case/{case_id}/ttp")
def get_ttps(
    case_id: str,
    auth: AuthContext = Depends(require_permission(PERM_CASE_READ))
):
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

@app.delete("/case/{case_id}/ttp/{ttp_id}")
def delete_ttp(
    case_id: str,
    ttp_id: str,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM case_ttps WHERE tenant_id = %s AND case_id = %s AND ttp_id = %s", (auth.tenant_id, case_id, ttp_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="TTP not found")
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    emit_event("nv.cases.ttp.deleted.v1", "TTPDeleted", {"case_id": case_id, "ttp_id": ttp_id}, auth)
    return {"status": "deleted"}
