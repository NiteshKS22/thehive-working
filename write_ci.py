content = r"""name: v5 Services CI

on:
  push:
    branches: [ main ]
    paths:
      - 'v5-core/**'
  pull_request:
    branches: [ main ]
    paths:
      - 'v5-core/**'

jobs:
  build-and-test:
    runs-on: ubuntu-20.04
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install Dependencies
        run: |
          pip install -r v5-core/alert-ingestion-service/requirements.txt
          pip install -r v5-core/dedup-correlation-service/requirements.txt
          pip install -r v5-core/correlation-service/requirements.txt
          pip install -r v5-core/query-api-service/requirements.txt
          pip install -r v5-core/case-service/requirements.txt
          pip install pytest httpx pyyaml pyjwt cryptography fastapi

      - name: Test Services (Unit)
        run: |
          pytest v5-core/alert-ingestion-service/tests/
          pytest v5-core/dedup-correlation-service/tests/
          pytest v5-core/correlation-service/tests/
          pytest v5-core/common/auth/tests/
          # pytest v5-core/case-service/tests/ (TODO: add tests)

      - name: Build Docker Images
        run: |
          cp -r v5-core/common v5-core/alert-ingestion-service/
          cp -r v5-core/common v5-core/query-api-service/
          cp -r v5-core/common v5-core/case-service/

          docker build -t thehive-ingestion:ci v5-core/alert-ingestion-service/
          docker build -t thehive-dedup:ci v5-core/dedup-correlation-service/
          docker build -t thehive-indexer:ci v5-core/opensearch-indexer-service/
          docker build -t thehive-query:ci v5-core/query-api-service/
          docker build -t thehive-correlation:ci v5-core/correlation-service/
          docker build -t thehive-group-indexer:ci v5-core/group-indexer-service/
          docker build -t thehive-case:ci v5-core/case-service/

      - name: Start v5 Stack
        working-directory: v5-core/event-spine
        run: |
           docker-compose up -d
           sleep 20

      - name: Apply Index Templates
        run: |
          curl -X PUT "http://localhost:9200/_index_template/alerts_template"             -H "Content-Type: application/json"             -d @v5-core/opensearch-indexer-service/OPENSEARCH_INDEX_TEMPLATE.json

          curl -X PUT "http://localhost:9200/_index_template/groups_template"             -H "Content-Type: application/json"             -d @v5-core/group-indexer-service/GROUPS_INDEX_TEMPLATE.json

      - name: Start App Services
        run: |
          NETWORK_NAME="event-spine_default"

          docker run -d --name ingestion-service --network              -p 8000:8000             -e KAFKA_BOOTSTRAP_SERVERS=redpanda:29092             -e JWT_SECRET="dev-secret-do-not-use-in-prod"             thehive-ingestion:ci

          docker run -d --name query-service --network              -p 8001:8001             -e OPENSEARCH_HOST=opensearch             -e POSTGRES_HOST=postgres             -e POSTGRES_PASSWORD=hive             -e JWT_SECRET="dev-secret-do-not-use-in-prod"             thehive-query:ci

          docker run -d --name case-service --network              -p 8002:8000             -e KAFKA_BOOTSTRAP_SERVERS=redpanda:29092             -e POSTGRES_HOST=postgres             -e POSTGRES_PASSWORD=hive             -e JWT_SECRET="dev-secret-do-not-use-in-prod"             thehive-case:ci

          docker run -d --name dedup-service --network              -e KAFKA_BOOTSTRAP_SERVERS=redpanda:29092             -e REDIS_HOST=redis             thehive-dedup:ci

          docker run -d --name indexer-service --network              -e KAFKA_BOOTSTRAP_SERVERS=redpanda:29092             -e OPENSEARCH_HOST=opensearch             thehive-indexer:ci

          docker run -d --name correlation-service --network              -e KAFKA_BOOTSTRAP_SERVERS=redpanda:29092             -e POSTGRES_HOST=postgres             -e POSTGRES_PASSWORD=hive             thehive-correlation:ci

          docker run -d --name group-indexer-service --network              -e KAFKA_BOOTSTRAP_SERVERS=redpanda:29092             -e OPENSEARCH_HOST=opensearch             thehive-group-indexer:ci

          sleep 10

      - name: Auth & Isolation Smoke Test (Ingestion/Query)
        run: |
          TOKEN_A=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyQSIsInRlbmFudF9pZCI6InRlbmFudC1BIiwicm9sZXMiOlsiU09DX0FOQUxZU1QiXSwiZXhwIjoxNzcxNDExODE4LCJpc3MiOiJodHRwczovL2F1dGguZXhhbXBsZS5jb20ifQ.AtDsCRT0TLpcG52z1McLauM_ha1u6Cy-Qdp7zJcnbgs
          TOKEN_B=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyQiIsInRlbmFudF9pZCI6InRlbmFudC1CIiwicm9sZXMiOlsiU09DX0FOQUxZU1QiXSwiZXhwIjoxNzcxNDExODE4LCJpc3MiOiJodHRwczovL2F1dGguZXhhbXBsZS5jb20ifQ.COLZEjft8E9e97vEh4kXW6JSD-aS1K82HV5wIPZr2PM

          # 1. Test Ingestion with Token A
          echo "Ingesting with Token A..."
          curl -v -X POST http://localhost:8000/ingest             -H "Authorization: Bearer "             -H "Content-Type: application/json"             -H "Idempotency-Key: auth-test-1"             -d '{"source": "ci", "type": "test", "sourceRef": "ref-a", "title": "Auth Test A", "host": "host-a", "rule_id": "R1_HOST_RULE"}'

          sleep 5

          # 2. Verify Tenant A cannot see Tenant B data
          echo "Querying Tenant A with Token A..."
          RESP_A=

          if echo "" | grep -q "Auth Test A"; then
             echo "SUCCESS: Tenant A sees its alert."
          else
             echo "FAILURE: Tenant A missing alert."
             """ + "exit 1" + r"""
          fi

      - name: Case Service Smoke Test
        run: |
          # Token with ADMIN role (has CASE_WRITE)
          TOKEN_ADMIN_A=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkEiLCJ0ZW5hbnRfaWQiOiJ0ZW5hbnQtQSIsInJvbGVzIjpbIlJPTEVfQURNSU4iXSwiZXhwIjoxNzcxNDExODE4LCJpc3MiOiJodHRwczovL2F1dGguZXhhbXBsZS5jb20ifQ.fk69HpDm9ffQVOeb0HEXvdGqrc29GNLu5LapE_v_DpI
          TOKEN_ANALYST_B=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyQiIsInRlbmFudF9pZCI6InRlbmFudC1CIiwicm9sZXMiOlsiUk9MRV9BTkFMWVNUIl0sImV4cCI6MTc3MTQxMTgxOSwiaXNzIjoiaHR0cHM6Ly9hdXRoLmV4YW1wbGUuY29tIn0.wc25IXCau-PMtp1C-qcnjEbJmA67_BspIEisHsrT9dE

          # 1. Create Case (Tenant A)
          echo "Creating Case..."
          CASE_RESP=
          
          echo "Create Response: "
          CASE_ID=

          if [ "" == "null" ]; then
             echo "FAILURE: Case creation failed"
             """ + "exit 1" + r"""
          fi

          # 2. Read Case via Query Service (Tenant A)
          echo "Reading Case (Tenant A)..."
          GET_RESP=
          
          if echo "" | grep -q "Incident Alpha"; then
             echo "SUCCESS: Case found."
          else
             echo "FAILURE: Case not found via Query Service. "
             """ + "exit 1" + r"""
          fi

          # 3. Verify Isolation (Tenant B)
          echo "Reading Case (Tenant B)..."
          GET_RESP_B=000
          
          if [ "" == "404" ]; then
             echo "SUCCESS: Tenant B cannot see Case A (404)."
          else
             echo "FAILURE: Tenant B got  (expected 404)."
             """ + "exit 1" + r"""
          fi

      - name: Stop Stack
        if: always()
        working-directory: v5-core/event-spine
        run: docker-compose down
"""
with open(".github/workflows/v5-ci.yml", "w") as f:
    f.write(content)
