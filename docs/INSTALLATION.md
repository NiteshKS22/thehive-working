# NeuralVyuha Installation Guide

## 1. Introduction
NeuralVyuha is a high-performance Security Incident Response Platform (SIRP) engine designed for modern Security Operations Centers (SOCs). This guide walks you through setting up the complete NeuralVyuha stack using Docker Compose.

## 2. Prerequisites
*   **Operating System**: Linux (Ubuntu 20.04+ recommended) or macOS.
*   **Docker Engine**: Version 20.10.0 or higher.
*   **Docker Compose**: Version 1.29.2 or higher.
*   **Hardware**: Minimum 8GB RAM, 4 vCPUs (for the full stack including OpenSearch and Redpanda).

## 3. Quick Start (Development/Testing)

### Step 3.1: Clone the Repository
```bash
git clone https://github.com/thehive-project/thehive-v5.git neural-vyuha
cd neural-vyuha
```

### Step 3.2: Configure Environment
The default configuration is set for a local development environment. For production, you **must** update the secrets.

1.  Navigate to the event spine directory:
    ```bash
    cd nv-core/event-spine
    ```
2.  (Optional) Create a `.env` file if you need to override defaults:
    ```bash
    touch .env
    # Add overrides like:
    # POSTGRES_PASSWORD=mysecretdbpass
    # JWT_SECRET=myproductionjwtsecret
    ```

### Step 3.3: Launch the Stack
```bash
docker-compose up -d
```

This command starts the following services:
*   **nv-redpanda**: High-performance streaming platform (Kafka API compatible).
*   **nv-redis**: Fast in-memory cache for deduplication.
*   **nv-postgres**: Relational database for Case Management (The Vault).
*   **nv-opensearch**: Search and analytics engine.
*   **nv-ingest**: Alert Ingestion Service.
*   **nv-dedup**: Deduplication & Correlation Service.
*   **nv-case-engine**: The Master of Record for Cases & Tasks.
*   **nv-query**: Unified Read API.
*   **nv-indexer**: Indexes data into OpenSearch.
*   **nv-correlation**: Real-time incident clustering engine.
*   **nv-group-indexer**: Indexes correlation groups.
*   **reverse-bridge**: Synchronizes v5 data back to legacy v4 API (optional).

### Step 3.4: Verify Installation
Check the status of all containers:
```bash
docker-compose ps
```
All containers should be in `Up (healthy)` state.

You can verify the API is reachable:
```bash
curl http://localhost:8001/healthz  # Query API
curl http://localhost:8002/healthz  # Case Engine
```

## 4. Post-Installation
*   **Access the UI**: (Assuming legacy UI integration) Navigate to `http://localhost:9000` (or your configured UI port).
*   **Default Credentials**:
    *   **User**: `admin@thehive.local` (or as configured in your initial setup script).
    *   **Password**: `secret` (Change immediately on first login!).

## 5. Troubleshooting
*   **"Kafka Connection Failed"**: Ensure `nv-redpanda` is healthy. Check logs: `docker-compose logs nv-redpanda`.
*   **"Database Connection Refused"**: Ensure `nv-postgres` is ready. It might take a few seconds to initialize on first run.
*   **"Permission Denied"**: If using bind mounts, ensure the user running docker has permission to write to the `data/` directories.

## 6. Upgrading
To upgrade to a newer version of NeuralVyuha:
1.  Pull the latest code: `git pull origin main`.
2.  Rebuild images: `docker-compose build`.
3.  Restart services: `docker-compose up -d`.

## 7. Starting Microservices (Manual Dev Mode)
By default, the `nv-core/event-spine/docker-compose.yml` only starts the infrastructure (Redpanda, Redis, Postgres, OpenSearch). To run the NeuralVyuha microservices, you must build and run them separately or add them to a full docker-compose file.

### 7.1 Creating a Full Stack Compose File
Create a new file `docker-compose.full.yml` in the root directory:

```yaml
version: '3.8'
services:
  # Infrastructure (Include or reference event-spine)
  # ... (Copy from event-spine or use extends)

  # Microservices
  nv-ingest:
    build: nv-core/nv-ingest
    image: nv-ingest:latest
    container_name: nv-ingest
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=nv-redpanda:29092
      - JWT_SECRET=dev-secret-do-not-use-in-prod
    ports:
      - "8000:8000"
    networks:
      - nv-mesh
    depends_on:
      nv-redpanda:
        condition: service_healthy

  nv-query:
    build: nv-core/nv-query
    image: nv-query:latest
    container_name: nv-query
    environment:
      - OPENSEARCH_HOST=nv-opensearch
      - POSTGRES_HOST=nv-postgres
      - POSTGRES_PASSWORD=hive
      - POSTGRES_DB=nv_vault
      - JWT_SECRET=dev-secret-do-not-use-in-prod
    ports:
      - "8001:8001"
    networks:
      - nv-mesh
    depends_on:
      nv-opensearch:
        condition: service_healthy
      nv-postgres:
        condition: service_healthy

  nv-case-engine:
    build: nv-core/nv-case-engine
    image: nv-case-engine:latest
    container_name: nv-case-engine
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=nv-redpanda:29092
      - POSTGRES_HOST=nv-postgres
      - POSTGRES_PASSWORD=hive
      - POSTGRES_DB=nv_vault
      - JWT_SECRET=dev-secret-do-not-use-in-prod
    ports:
      - "8002:8000"
    networks:
      - nv-mesh
    depends_on:
      nv-redpanda:
        condition: service_healthy
      nv-postgres:
        condition: service_healthy

  # ... (Add nv-dedup, nv-indexer, nv-correlation, nv-group-indexer similarly)

networks:
  nv-mesh:
    external: true # Or define if running standalone
```

### 7.2 Running
```bash
# 1. Start Infrastructure
cd nv-core/event-spine
docker-compose up -d

# 2. Build and Start Services
cd ../..
docker-compose -f docker-compose.full.yml up -d --build
```
