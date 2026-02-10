from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

app = FastAPI(title="TheHive v5-Internal Ingestor Prototype")

class IngestRequest(BaseModel):
    source: str
    type: str
    data: dict

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "v5-proto"}

@app.post("/ingest")
def ingest_alert(item: IngestRequest):
    # Minimal prototype logic
    # In a real impl, this would push to an event bus or v5 storage
    print(f"Received ingestion request from {item.source}")
    return {"status": "accepted", "id": "proto-12345"}
