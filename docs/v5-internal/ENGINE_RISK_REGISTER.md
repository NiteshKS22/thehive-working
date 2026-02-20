# Engine Risk Register

**Status**: Baseline (Phase E1)
**Last Updated**: 2026-02-11

This document tracks known security, reliability, and operational risks for the v5-Internal engine.

## Scoring Legend
- **Impact**: Low / Medium / High / Critical
- **Likelihood**: Unlikely / Possible / Likely
- **Residual Risk**: L / M / H / C

| ID | Title | Category | Impact | Likelihood | Current Controls | Gaps | Mitigation Plan | Owner | Status | Residual | Evidence |
|----|-------|----------|--------|------------|------------------|------|-----------------|-------|--------|----------|----------|
| R-001 | Auth Misconfiguration (RS256) | Security | Critical | Possible | Startup Guardrail checks keys | Auto-rotation missing | E2: Implement JWKS rotation | SecArch | In Progress | M | `middleware.py` |
| R-002 | DEV_MODE Privilege Escalation | Security | Critical | Unlikely | Strict `ALLOW_DEV_OVERRIDES` check | Env var leaks | E5: Secrets Mgmt (Vault) | Ops | Mitigated | L | `middleware.py` |
| R-003 | Tenant Isolation Regression | Security | Critical | Unlikely | Middleware Enforcement + Query Filters | Manual code reviews | E2: Granular Perms Policy Enforcement | Backend | Mitigated | L | `v5-ci.yml` |
| R-004 | OpenSearch Index Corruption | Data | High | Unlikely | Query API validates tenant_id on fetch | None | E4: Index Checksums | Ops | Accepted | M | `query-api-service/app/main.py` |
| R-005 | At-Most-Once Data Loss | Reliability | High | Possible | Commit only on success/DLQ | DLQ could fill up | E4: DLQ Monitoring/Alerts | Ops | In Progress | M | `correlation-service/app/main.py` |
| R-006 | Backpressure / Consumer Lag | Performance | High | Likely | None (Redpanda buffers) | No Autoscaling | E4: KEDA Autoscaling | Ops | Open | H | `docker-compose.yml` (limits) |
| R-007 | DLQ Silent Growth | Operational | Medium | Likely | Logs errors | No Metric Alerts | E5: Prometheus Alerts | Ops | Open | M | `main.py` (logs) |
| R-008 | Topic Retention Data Loss | Data | High | Unlikely | Default Redpanda config | Explicit retention policy | E5: Terraform Topic Mgmt | Ops | Open | M | - |
| R-009 | Replay Storms | Performance | High | Possible | Idempotent consumers | Rate limiting missing | E4: Consumer Rate Limiting | Backend | Open | M | - |
| R-010 | Redis Persistence Failure | Reliability | Medium | Unlikely | AOF Enabled | Disk fill monitoring | E5: Disk Alerts | Ops | Mitigated | L | `docker-compose.yml` |
| R-011 | Postgres Lock Contention | Performance | Medium | Possible | Row-level locking | Pool sizing tuning | E4: PgBouncer | Backend | Open | M | `db.py` |
| R-012 | Broad Correlation Rules | Operational | Medium | Likely | Governance (Disable Rule) | No Anomaly Detection | E5: Rule Analytics | Lead | Open | M | `PHASE3E_3F_RUNBOOK.md` |
| R-013 | Correlation False Negatives | Operational | Medium | Possible | Governance (Simulate) | ML assistance | E6: AI Tuning | Lead | Open | M | - |
| R-014 | Schema Breaking Changes | Reliability | High | Possible | Schema Versioning in Payload | No Schema Registry | E5: Schema Registry | Backend | Open | H | `EVENT_MODEL.md` |
| R-015 | Secrets in Env Vars | Security | High | Likely | Container Injection | No Vault/Rotation | E5: Vault Integration | SecArch | Open | H | `docker-compose.yml` |
| R-016 | No mTLS (Flat Network) | Security | High | Likely | None (Internal Docker Net) | Encrypted Transit | E2: Service Mesh / mTLS | SecArch | Open | H | `docker-compose.yml` |
| R-017 | No Service-to-Service Auth | Security | Medium | Likely | None (Implicit Trust) | Internal JWTs | E2: S2S Tokens | SecArch | Open | M | - |
| R-018 | CI Flakiness (Race Conditions) | Reliability | Low | Possible | `wait-for-it` logic | Strict Healthchecks | E4: Robust Probes | QA | Mitigated | L | `v5-ci.yml` |
| R-019 | Audit Volume Costs | Operational | Low | Likely | Structured Logs | Log Sampling | E5: Log Retention Policy | Ops | Accepted | L | `audit.py` |
| R-020 | Index Retention Manual | Operational | Medium | Likely | Monthly Indices | ISM Policies | E5: Auto ISM Config | Ops | Open | M | `RETENTION.md` |
| R-021 | ID Collision (UUIDv4) | Data | Critical | Unlikely | UUIDv4 (122 bits) | None | Accepted Risk | Arch | Accepted | L | `main.py` |
| R-022 | Observability Gaps | Operational | High | Likely | Logs | Metrics/Dashboards | E5: Grafana Boards | Ops | Open | H | - |
| R-023 | RBAC Wiring Mistakes | Security | High | Unlikely | Unit Tests | Policy as Code | E2: Granular Perms | SecArch | Mitigated | M | `test_middleware.py` |
| R-024 | Data Residency / PII | Compliance | High | Unlikely | Tenant Isolation | PII Masking | E2: Field Encryption | Legal | Open | H | - |
| R-025 | v4 Bridge Absence | Strategic | Critical | Certain | None | Manual Parallel Run | E3: v4-Bridge Sync | PM | Open | C | `MASTER_ENGINE_STATE.md` |

## Risk Acceptance Rationale
- **R-025 (v4 Bridge)**: Accepted for Phase E1. Migration strategy (Phase 4) will address this.
- **R-021 (UUID Collision)**: Mathematical improbability accepted standard industry practice.
- **R-016 (mTLS)**: Deferring to Platform Phase (E2) to avoid complexity spikes now.
| R-026 | Authorization Bypass (Role-Only) | Security | Critical | Unlikely | Middleware requires permissions, not just roles | None | E2: Granular RBAC | SecArch | Closed | L | `rbac.py` |
| R-027 | Case Data Leakage | Data | High | Unlikely | Tenant Isolation in PK + AuthContext | None | E3: CI Tests | Backend | Mitigated | L | `v5-ci.yml` |
| R-028 | Case Idempotency Failure | Reliability | Medium | Possible | Manual UUIDs + DB Constraints | None | E3: Idempotency Keys | Backend | Mitigated | L | `main.py` |
| R-029 | DLQ Outage Blocking | Operational | High | Possible | Consumer halts if DLQ fails | Alerts | E4.1: Monitor DLQ health | Ops | Mitigated | M | `dlq.py` |
| R-030 | Replay Storm Overload | Operational | Medium | Likely | Backpressure + Rate Limiting | None | E4.2: CI Burst Test | Backend | Mitigated | L | `backpressure.py` |
| R-031 | Observability Gaps | Operational | High | Likely | Prometheus Metrics + Health Checks | None | E4.3: Dashboards | Ops | Mitigated | L | `metrics.py` |
| R-032 | Secret Leakage via Env | Security | High | Unlikely | Secrets Loader (File Priority) | None | E5: Vault | Ops | Mitigated | L | `secrets.py` |
| R-033 | Auth Key Compromise | Security | Critical | Unlikely | RS256 + Key Rotation | None | E5: OIDC | SecArch | Mitigated | L | `oidc.py` |
| R-034 | API Abuse (DoS) | Operational | High | Possible | Rate Limiting Middleware | Distributed State | E5: Redis Limiter | Backend | Mitigated | M | `rate_limit.py` |
