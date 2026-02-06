# Maintenance Guide

## Monthly Patch Cadence
- Review Dependabot PRs weekly.
- Release a patch version (e.g., 4.1.25) monthly if there are security updates.
- Run `sbt test` and `sbt docker:publishLocal` locally before merging complex changes.

## Running Scans
- **Trivy**: `trivy image thehiveproject/thehive:latest`
- **Dependency Check**: Runs in CI. Check `reports/` artifact.
- **SBOM**: Generated in CI as `sbom.json`.

## Handling Vulnerabilities
- Triage Criticals in Dependabot/Trivy reports.
- If false positive, add to `suppressions.xml` (Dependency Check) or `.trivyignore` (Trivy) with a comment explaining why.
