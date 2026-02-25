# ADR-039: Documentation-as-Code & UI Help Injection Strategy

## Status
Accepted

## Context
As NeuralVyuha (NV) transitions to production, maintaining separate documentation repositories and UI help files creates synchronization issues. The "Help Center" in the UI must reflect the latest architectural decisions and API specifications without manual copy-pasting.

## Decision
We adopt a **"Docs-as-Code"** strategy with the following components:

1.  **Single Source of Truth**: GitHub Markdown files in `docs/` are the authoritative source.
    *   `INSTALLATION.md`: Setup guide.
    *   `ARCHITECTURE.md`: High-level design.
    *   `API_REFERENCE.md`: Endpoint specifications.
    *   `USER_MANUAL.md`: Aggregated manual for end-users.

2.  **Aggregation Pipeline**:
    *   A Python script (`tools/generate_manual.py`) merges individual topic files into a comprehensive `USER_MANUAL.md`.
    *   This script runs during CI/CD to ensure the manual is always up-to-date with code changes.

3.  **UI Injection**:
    *   The NeuralVyuha UI consumes documentation via a dedicated `NvHelpCtrl`.
    *   For Phase D1, the UI displays a curated "Quick Help" (Introduction, Triage, Timeline) and links to the full generated manual.
    *   Future phases will fetch the manual content dynamically via API (GET /docs).

## Consequences
*   **Consistency**: UI help and GitHub docs are synchronized.
*   **Maintainability**: Developers update docs alongside code (in the same PR).
*   **Accessibility**: SOC analysts access help directly within their workflow.
*   **Automation**: Manual generation is automated, reducing human error.

## Governance
*   All new features (Phase E7+) must include an update to the relevant markdown file in `docs/`.
*   The `generate_manual.py` script must pass in CI before merging.
