# Rollback Procedure

## Procedure
1. Stop the service: `docker-compose down`.
2. Revert `docker-compose.yml` to previous image tag.
3. Restore Database backup if a schema migration occurred (check logs).
   - If no schema change, data is usually backward compatible for minor patches.
4. Start service: `docker-compose up -d`.

## Database
- Cassandra: Restore snapshot.
- Elasticsearch: Restore snapshot.
