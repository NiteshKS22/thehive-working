import time
import uuid
import json
import logging
import sys
import os
import psycopg2
from fastapi import FastAPI, Header, HTTPException, Response, status, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Import Auth Middleware
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../common')))
from auth.middleware import get_auth_context, AuthContext, validate_auth_config, require_permission
from auth.rbac import PERM_CASE_READ, PERM_CASE_WRITE
from observability.metrics import MetricsMiddleware, get_metrics_response
from observability.health import global_health_registry
from config.secrets import get_secret

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

class UpdateCaseRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[int] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None

class CreateTaskRequest(BaseModel):
    title: str
    assigned_to: Optional[str] = None

class CreateNoteRequest(BaseModel):
    body: str

class LinkAlertRequest(BaseModel):
    original_event_id: str
    link_reason: Optional[str] = None

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
                INSERT INTO cases (tenant_id, case_id, title, description, severity, tlp, pap, status, created_by, assigned_to, created_at, updated_at, entity_version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'OPEN', %s, %s, %s, %s, 1)
                """,
                (auth.tenant_id, case_id, req.title, req.description, req.severity, req.tlp, req.pap, auth.user_id, req.assignee, now, now)
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

    emit_event("cases.created.v1", "CaseCreated", {
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

    emit_event("cases.updated.v1", "CaseUpdated", {
        "case_id": case_id,
        "updates": req.model_dump(exclude_unset=True),
        "updated_by": auth.user_id,
        "version": new_version
    }, auth)

    if req.status == 'CLOSED':
         emit_event("cases.closed.v1", "CaseClosed", {"case_id": case_id, "closed_by": auth.user_id}, auth)

    return resp_body

# ... (Other endpoints: tasks, notes, links - omitted for brevity, similar pattern)
# For T2 scope, focus was on Case creation/update.
