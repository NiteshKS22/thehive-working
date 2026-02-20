import time
import uuid
import json
import logging
import sys
import os
from fastapi import FastAPI, Header, HTTPException, Response, status, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Import Auth Middleware
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../common')))
from auth.middleware import get_auth_context, AuthContext, validate_auth_config, require_permission
from auth.rbac import PERM_ALERT_INGEST
from observability.metrics import MetricsMiddleware, get_metrics_response
from observability.health import global_health_registry

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("ingest-service")

app = FastAPI(title="TheHive v5 Ingestion Service")

# Observability
app.add_middleware(MetricsMiddleware, service_name="alert-ingestion-service")

@app.on_event("startup")
def startup_event():
    validate_auth_config()
    
    # Health Checks
    def check_kafka():
        return producer and producer.bootstrap_connected()
    
    global_health_registry.add_check("kafka", check_kafka)

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:29092")
TOPIC_NAME = "alerts.ingest.v1"

try:
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    logger.info("Kafka producer initialized")
except Exception as e:
    logger.error(f"Failed to initialize Kafka producer: {e}")
    producer = None

class Alert(BaseModel):
    source: str
    type: str
    sourceRef: str
    title: str
    description: Optional[str] = None
    # tenant_id REMOVED from user input
    severity: int = Field(default=2, ge=1, le=4)
    tlp: int = Field(default=2, ge=0, le=3)
    pap: int = Field(default=2, ge=0, le=3)
    artifacts: list = []

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

@app.get("/health") # Legacy alias
def health_check():
    return healthz()

@app.post("/ingest", status_code=202)
async def ingest_alert(
    alert: Alert,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    trace_id: Optional[str] = Header(None, alias="X-Trace-Id"),
    auth: AuthContext = Depends(require_permission(PERM_ALERT_INGEST)) # Require Permission
):
    if not trace_id:
        trace_id = str(uuid.uuid4())

    # Construct Event
    event = {
        "event_id": str(uuid.uuid4()),
        "trace_id": trace_id,
        "tenant_id": auth.tenant_id, # Enforced
        "idempotency_key": idempotency_key,
        "timestamp": int(time.time() * 1000),
        "schema_version": "1.0",
        "payload": alert.model_dump()
    }
    event['payload']['tenant_id'] = auth.tenant_id

    if producer:
        try:
            producer.send(TOPIC_NAME, value=event)
            logger.info(f"Published event {event['event_id']} trace_id={trace_id} tenant={auth.tenant_id}")
        except KafkaError as e:
            logger.error(f"Failed to publish event: {e}")
            raise HTTPException(status_code=500, detail="Event publication failed")
    else:
        logger.warning(f"Dry-run (no producer): {event['event_id']}")

    return {"status": "accepted", "event_id": event['event_id'], "trace_id": trace_id}
