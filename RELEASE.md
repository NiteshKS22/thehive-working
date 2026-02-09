# Release Process

## Versioning
- Scheme: `v4-lts.x` (e.g. `4.1.25`).
- Current version is defined in `build.sbt`.

## Release Checklist
1. Create a release branch `release/x.y.z`.
2. Update `build.sbt` version.
3. Update `CHANGELOG.md`.
4. Run full CI pipeline.
5. Verify SBOM and Scan reports.
6. Merge to `main`.
7. Tag the release `vX.Y.Z`.
8. CI will build and push the docker image.

## Artifacts
- Docker Image: `thehiveproject/thehive:X.Y.Z`
- SBOM: `sbom.json`
- Source Tarball.
