# Maintenance Guide

## Monthly Patch Cadence
- Review Dependabot PRs weekly.
- Release a patch version (e.g., 4.1.25) monthly if there are security updates.
- Run `sbt test` and `sbt docker:publishLocal` locally before merging complex changes.

## Vulnerability Management Policy

### Service Level Agreements (SLA)
We aim to address vulnerabilities within the following timelines after discovery:
- **Critical**: Fix or suppress with mitigation within **7 days**.
- **High**: Fix or suppress with mitigation within **30 days**.
- **Medium/Low**: Triage and prioritize for next scheduled release.

### Suppression Policy
Suppressions in `suppressions.xml` (backend) or `.trivyignore` (container) are allowed ONLY when:
1. **False Positive**: The tool has misidentified the component or the CVE does not apply (e.g., code path not used).
2. **Mitigated**: External controls (WAF, network segmentation) or internal config effectively nullify the risk.
3. **Acceptable Risk**: The impact is negligible in our specific internal context.

**Requirement:** Every suppression MUST include a comment with:
- The rationale (False Positive / Mitigated).
- A reference to an internal ticket or investigation note.
- Date added.

## Running Scans
- **Trivy**: `trivy image thehiveproject/thehive:latest`
- **Dependency Check**: Runs in CI. Check `reports/` artifact.
- **SBOM**: Generated in CI as `sbom.json`.

## Frontend Build Requirements
- **Node.js**: v12 (Pinned in CI)
- **npm**: Compatible with Node 12 (pinned in CI)
- **Bower**: v1.x (Installed via npm)
- **Grunt**: v1.x (Installed via npm)

## Handling Vulnerabilities
- Triage Criticals in Dependabot/Trivy reports.
- If false positive, add to `suppressions.xml` (Dependency Check) or `.trivyignore` (Trivy) with a comment explaining why.
