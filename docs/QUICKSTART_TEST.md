# Quick Start for Testing NeuralVyuha

This guide is designed for developers or QA engineers who want to spin up the entire NeuralVyuha stack locally for testing purposes.

## Prerequisites
*   Docker & Docker Compose installed.
*   Git installed.

## Step 1: Clone the Repository
```bash
git clone https://github.com/thehive-project/thehive-v5.git neural-vyuha
cd neural-vyuha
```

## Step 2: Build and Start Services
We use Docker Compose to orchestrate the entire environment (Event Spine + Microservices).

1.  Navigate to the core directory:
    ```bash
    cd nv-core/event-spine
    ```

2.  (Optional) Clean up any old volumes to ensure a fresh state:
    ```bash
    docker-compose down -v
    ```

3.  Start the stack in detached mode:
    ```bash
    docker-compose up -d --build
    ```

    *Note: The first build might take 5-10 minutes as it pulls base images and installs Python dependencies.*

4.  Wait for services to become healthy:
    ```bash
    # Watch the status until all show (healthy)
    watch docker-compose ps
    ```

## Step 3: Initialize Data (Index Templates)
Once OpenSearch is running (check `nv-opensearch` status), apply the index templates manually if not done by CI:

```bash
# From the root of the repo (open a new terminal)
curl -X PUT "http://localhost:9200/_index_template/alerts_template" \
  -H "Content-Type: application/json" \
  -d @nv-core/nv-indexer/OPENSEARCH_INDEX_TEMPLATE.json

curl -X PUT "http://localhost:9200/_index_template/groups_template" \
  -H "Content-Type: application/json" \
  -d @nv-core/nv-group-indexer/GROUPS_INDEX_TEMPLATE.json
```

## Step 4: Run Smoke Tests
We have a built-in script to verify the core loop (Ingest -> Kafka -> Index -> Query).

1.  Install test dependencies (local python):
    ```bash
    pip install requests
    ```

2.  Run the UI Routing verification script (verifies API reachability):
    ```bash
    # You need a valid JWT token. For local dev, services might be in dev mode or use a mock token.
    # Export a dev token if you have the generator, or use the dev mode headers if enabled.
    export QUERY_API_URL=http://localhost:8001
    python .github/scripts/verify_ui_routing.py
    ```

## Step 5: Manual Testing via UI
1.  Open your browser to `http://localhost:9000` (The Legacy UI Shell).
2.  Login with default credentials:
    *   **User**: `admin@thehive.local`
    *   **Password**: `secret`
3.  Navigate to **NeuralVyuha Incidents** in the sidebar.
4.  Navigate to **Help Center** to learn more.

## Step 6: Triggering Data
You can simulate alerts using `curl`:

```bash
# Note: Requires a valid JWT token in <YOUR_JWT>
curl -X POST http://localhost:8000/alerts \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(date +%s)" \
  -H "Authorization: Bearer <YOUR_JWT>" \
  -d '{
    "title": "Suspicious Login",
    "description": "Failed login attempt from IP 1.2.3.4",
    "severity": 2,
    "source": "manual-test",
    "sourceRef": "alert-001",
    "artifacts": [{"dataType": "ip", "data": "1.2.3.4"}]
  }'
```

Check the **NeuralVyuha Incidents** dashboard after a few seconds to see if it appears (grouped).

## Step 7: Teardown
To stop everything:
```bash
cd nv-core/event-spine
docker-compose down
```
