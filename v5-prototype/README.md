# v5-Internal Prototype

This is a scaffolding prototype for the v5-Internal architecture.

## Components
- **Ingestor**: FastAPI-based service for alert ingestion (skeleton).

## Running
```bash
docker build -t v5-proto .
docker run -p 8000:8000 v5-proto
```

## API
- `GET /health`: Health check.
- `POST /ingest`: Sample ingestion endpoint.
