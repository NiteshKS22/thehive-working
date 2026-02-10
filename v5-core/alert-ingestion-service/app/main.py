import time
import uuid
import json
import logging
from fastapi import FastAPI, Header, HTTPException, Response, status
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("ingest-service")

app = FastAPI(title="TheHive v5 Ingestion Service")

# Configuration
KAFKA_BOOTSTRAP_SERVERS = "redpanda:29092"
TOPIC_NAME = "alerts.ingest.v1"

# Initialize Kafka Producer
# In production, use a more robust client (confluent-kafka) or DI framework
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
    tenant_id: str = "default"
    severity: int = Field(default=2, ge=1, le=4)
    tlp: int = Field(default=2, ge=0, le=3)
    pap: int = Field(default=2, ge=0, le=3)
    artifacts: list = []

    class Config:
        schema_extra = {
            "example": {
                "source": "kibana",
                "type": "external",
                "sourceRef": "alert-123",
                "title": "Suspicious Activity",
                "description": "Detected by SIEM",
                "severity": 3
            }
        }

@app.get("/health")
def health_check():
    if producer and producer.bootstrap_connected():
        return {"status": "ok", "kafka": "connected"}
    # Return ok for liveness even if kafka is down, readiness would fail
    return {"status": "ok", "kafka": "disconnected"}

@app.post("/ingest", status_code=202)
async def ingest_alert(
    alert: Alert,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    trace_id: Optional[str] = Header(None, alias="X-Trace-Id")
):
    if not trace_id:
        trace_id = str(uuid.uuid4())

    # 1. Validation (handled by Pydantic)

    # 2. Construct Event
    event = {
        "event_id": str(uuid.uuid4()),
        "trace_id": trace_id,
        "idempotency_key": idempotency_key,
        "timestamp": int(time.time() * 1000),
        "schema_version": "1.0",
        "payload": alert.model_dump()
    }

    # 3. Publish to Event Spine
    if producer:
        try:
            producer.send(TOPIC_NAME, value=event)
            # In sync mode we might wait, but for throughput we fire and forget or await ack
            # producer.flush()
            logger.info(f"Published event {event['event_id']} trace_id={trace_id}")
        except KafkaError as e:
            logger.error(f"Failed to publish event: {e}")
            raise HTTPException(status_code=500, detail="Event publication failed")
    else:
        logger.warning(f"Dry-run (no producer): {event['event_id']}")

    return {"status": "accepted", "event_id": event['event_id'], "trace_id": trace_id}
