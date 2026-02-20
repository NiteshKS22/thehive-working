import time
import uuid
import json
import logging
import sys
import os
import psycopg2
from fastapi import FastAPI, HTTPException, Response, status, Depends, Body, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Mount Common Auth
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../common')))
from auth.middleware import get_auth_context, AuthContext, validate_auth_config, require_permission
from auth.rbac import PERM_CASE_READ, PERM_CASE_WRITE
from observability.metrics import MetricsMiddleware, get_metrics_response
from observability.health import global_health_registry

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("case-service")

app = FastAPI(title="TheHive v5 Case Service")

app.add_middleware(MetricsMiddleware, service_name="case-service")

@app.on_event("startup")
def startup_event():
    validate_auth_config()
    
    def check_pg():
        try:
            conn = get_db_conn()
            conn.close()
            return True
        except:
            return False
            
    def check_kafka():
        return producer and producer.bootstrap_connected()
        
    global_health_registry.add_check("postgres", check_pg)
    global_health_registry.add_check("kafka", check_kafka)

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:29092")
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_PORT = int(os.getenv("POSTGRES_PORT", 5432))
PG_DB = os.getenv("POSTGRES_DB", "v5_events")
PG_USER = os.getenv("POSTGRES_USER", "hive")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "hive")

try:
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    logger.info("Kafka producer initialized")
except Exception as e:
    logger.error(f"Failed to initialize Kafka producer: {e}")
    producer = None

def get_db_conn():
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, database=PG_DB, user=PG_USER, password=PG_PASSWORD
        )
        return conn
    except Exception as e:
        logger.error(f"DB Connection failed: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

def emit_event(topic: str, event_type: str, payload: dict, auth: AuthContext, trace_id: str = None):
    if not producer:
        logger.warning(f"Skipping event emission (no producer): {event_type}")
        return

    if not trace_id:
        trace_id = str(uuid.uuid4())

    event = {
        "event_id": str(uuid.uuid4()),
        "trace_id": trace_id,
        "tenant_id": auth.tenant_id,
        "timestamp": int(time.time() * 1000),
        "schema_version": "1.0",
        "type": event_type,
        "payload": payload
    }
    # Ensure tenant_id is in payload too for convenience
    event['payload']['tenant_id'] = auth.tenant_id

    try:
        producer.send(topic, value=event)
        logger.info(f"Emitted {event_type} event_id={event['event_id']}")
    except KafkaError as e:
        logger.error(f"Failed to emit event: {e}")
        # Fail-Open? For auditing, maybe. But if we can't emit "CaseCreated", downstream might miss it.
        # But we wrote to DB. So we are consistent.
        pass

# Models
class CreateCaseRequest(BaseModel):
    title: str
    description: Optional[str] = None
    severity: int = Field(default=2, ge=1, le=4)
    assigned_to: Optional[str] = None

class UpdateCaseRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[int] = Field(None, ge=1, le=4)
    assigned_to: Optional[str] = None
    status: Optional[str] = Field(None, regex="^(OPEN|CLOSED)$")

class CreateTaskRequest(BaseModel):
    title: str
    assigned_to: Optional[str] = None

class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = Field(None, regex="^(OPEN|DONE|CANCELLED)$")
    assigned_to: Optional[str] = None

class CreateNoteRequest(BaseModel):
    body: str

class LinkAlertRequest(BaseModel):
    original_event_id: str
    link_reason: Optional[str] = None

# Endpoints

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

@app.post("/cases", status_code=201)
def create_case(
    req: CreateCaseRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    case_id = str(uuid.uuid4())
    created_at = int(time.time() * 1000)
    updated_at = created_at
    
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cases (tenant_id, case_id, title, description, severity, status, created_by, assigned_to, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 'OPEN', %s, %s, %s, %s)
                """,
                (auth.tenant_id, case_id, req.title, req.description, req.severity, auth.user_id, req.assigned_to, created_at, updated_at)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    emit_event("cases.created.v1", "CaseCreated", {
        "case_id": case_id,
        "title": req.title,
        "created_by": auth.user_id
    }, auth)

    return {"case_id": case_id, "status": "created"}

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
            
            # Get total count (simplified)
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

@app.patch("/cases/{case_id}")
def update_case(
    case_id: str,
    req: UpdateCaseRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    conn = get_db_conn()
    updated_at = int(time.time() * 1000)
    
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
            
    if not fields:
        return {"status": "no_change"}
        
    fields.append("updated_at = %s")
    params.append(updated_at)
    
    params.append(auth.tenant_id)
    params.append(case_id)
    
    try:
        with conn.cursor() as cur:
            sql = f"UPDATE cases SET {', '.join(fields)} WHERE tenant_id = %s AND case_id = %s"
            cur.execute(sql, tuple(params))
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

    emit_event("cases.updated.v1", "CaseUpdated", {
        "case_id": case_id,
        "updates": req.model_dump(exclude_unset=True),
        "updated_by": auth.user_id
    }, auth)
    
    if req.status == 'CLOSED':
         emit_event("cases.closed.v1", "CaseClosed", {"case_id": case_id, "closed_by": auth.user_id}, auth)

    return {"status": "updated"}

@app.post("/cases/{case_id}/tasks")
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
            # Check case existence
            cur.execute("SELECT 1 FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Case not found")
                
            cur.execute(
                """
                INSERT INTO case_tasks (tenant_id, case_id, task_id, title, status, created_by, assigned_to, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 'OPEN', %s, %s, %s, %s)
                """,
                (auth.tenant_id, case_id, task_id, req.title, auth.user_id, req.assigned_to, now, now)
            )
            # Update case updated_at
            cur.execute("UPDATE cases SET updated_at = %s WHERE tenant_id = %s AND case_id = %s", (now, auth.tenant_id, case_id))
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
    emit_event("cases.task.created.v1", "CaseTaskCreated", {
        "case_id": case_id,
        "task_id": task_id,
        "title": req.title
    }, auth)
    
    return {"task_id": task_id}

@app.post("/cases/{case_id}/notes")
def create_note(
    case_id: str,
    req: CreateNoteRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    note_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Case not found")
                
            cur.execute(
                """
                INSERT INTO case_notes (tenant_id, case_id, note_id, body, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (auth.tenant_id, case_id, note_id, req.body, auth.user_id, now)
            )
            # Update case updated_at
            cur.execute("UPDATE cases SET updated_at = %s WHERE tenant_id = %s AND case_id = %s", (now, auth.tenant_id, case_id))
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
    emit_event("cases.note.added.v1", "CaseNoteAdded", {
        "case_id": case_id,
        "note_id": note_id
    }, auth)
    
    return {"note_id": note_id}

@app.post("/cases/{case_id}/alerts")
def link_alert(
    case_id: str,
    req: LinkAlertRequest,
    auth: AuthContext = Depends(require_permission(PERM_CASE_WRITE))
):
    now = int(time.time() * 1000)
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM cases WHERE tenant_id = %s AND case_id = %s", (auth.tenant_id, case_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Case not found")
            
            # Idempotent insert
            cur.execute(
                """
                INSERT INTO case_alert_links (tenant_id, case_id, original_event_id, linked_by, linked_at, link_reason)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, case_id, original_event_id) DO NOTHING
                """,
                (auth.tenant_id, case_id, req.original_event_id, auth.user_id, now, req.link_reason)
            )
            
            if cur.rowcount > 0:
                cur.execute("UPDATE cases SET updated_at = %s WHERE tenant_id = %s AND case_id = %s", (now, auth.tenant_id, case_id))
                
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
    emit_event("cases.alert.linked.v1", "CaseAlertLinked", {
        "case_id": case_id,
        "original_event_id": req.original_event_id
    }, auth)
    
    return {"status": "linked"}

@app.get("/cases/{case_id}/timeline")
def get_timeline(case_id: str, auth: AuthContext = Depends(require_permission(PERM_CASE_READ))):
    conn = get_db_conn()
    timeline = []
    try:
        with conn.cursor() as cur:
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
