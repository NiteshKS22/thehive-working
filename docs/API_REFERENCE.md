# NeuralVyuha API Reference

## Base URL
All endpoints are relative to the service base URL (e.g., `http://localhost:8000` for Ingest, `http://localhost:8001` for Query).

## Authentication
All API requests require a valid JWT in the `Authorization` header:
`Authorization: Bearer <token>`

## 1. Alert Ingestion (nv-ingest)

### POST /alerts
Ingest a new alert.
*   **Request Body**: JSON (Schema validated).
*   **Headers**: `Idempotency-Key` (Required).
*   **Response**: `201 Created` with `{ "id": "uuid", "status": "accepted" }`.

## 2. Query API (nv-query)

### GET /alerts
Search for alerts.
*   **Parameters**:
    *   `q`: Search query string (Lucene syntax).
    *   `limit`: Max results (default 10).
    *   `sort`: Sort field (e.g., `-timestamp`).
*   **Response**: JSON array of alerts.

### GET /groups (Incidents)
List correlation groups (Vyuha).
*   **Parameters**:
    *   `status`: Filter by status (OPEN, CLOSED).
    *   `severity`: Filter by severity (1-4).
*   **Response**: JSON array of groups with metadata.

### GET /cases
List cases from the Master of Record.
*   **Parameters**: standard pagination/filtering.
*   **Response**: JSON array of cases.

## 3. Case Management (nv-case-engine)

### POST /cases
Create a new case.
*   **Request Body**: `{ "title": "string", "description": "string", "severity": 2, ... }`
*   **Headers**: `Idempotency-Key` (Required).
*   **Response**: `201 Created` with Case ID.

### PATCH /cases/{id}
Update a case.
*   **Request Body**: JSON patch.
*   **Response**: `200 OK` with updated version number.

### POST /cases/{id}/tasks
Add a task to a case.
*   **Request Body**: `{ "title": "string", ... }`
*   **Response**: `201 Created` with Task ID.

### POST /tasks/{id}/logs
Add a log/note to a task.
*   **Request Body**: `{ "message": "string", ... }`
*   **Response**: `201 Created` with Log ID.

## 4. Health & Metrics

### GET /healthz
Liveness probe. Returns `200 OK`.

### GET /readyz
Readiness probe. Checks dependencies (DB, Kafka).

### GET /metrics
Prometheus metrics endpoint.
