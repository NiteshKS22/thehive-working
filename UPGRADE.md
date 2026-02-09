# Upgrade Guide

## Operator Steps
1. Backup Database (Cassandra/BerkeleyDB) and Index (Elasticsearch/Lucene).
2. Pull new Docker image.
3. Update `docker-compose.yml` with new tag.
4. Run `docker-compose up -d`.
5. Check logs for migration messages.

## Config Compatibility
- This LTS branch maintains API compatibility.
- Check `CHANGELOG.md` for any config deprecations.

## Data Migration
- Phase 0 aims for zero schema changes.
- If migration is needed, it will be automated by `bin/migrate` on startup.
