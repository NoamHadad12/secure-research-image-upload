# Ralph Progress Log

Append-only notes for future iterations. Task truth lives in `prd.json`; this
file records decisions and evidence that should survive a fresh context.

## 2026-08-23 - Planning baseline

- Repository started clean with one initial commit and only `README.md`.
- Chosen stack: Dockerized Python 3.12/FastAPI backend, React/TypeScript frontend,
  PostgreSQL metadata, private MinIO object storage.
- Local Python is 32-bit 3.8, so Docker avoids a host runtime upgrade and makes
  reviewer setup reproducible.
- Primary invariant: all upload-record access is scoped by authenticated company
  before any MinIO operation or presigned URL generation.
- Foreign and nonexistent IDs intentionally share the same 404 response.
- Added `pending_upload` to avoid falsely marking a pre-upload row as uploaded.
- Browser-facing and Docker-internal MinIO endpoints must be configured
  separately; signed URL hostnames must not be rewritten.
- Planning artifacts are complete. No product code has been implemented.
- Next eligible story after Human Gate A: R01.

## 2026-08-23 - R01 scaffold backend and frontend workspaces

- Human Gate A was approved; implementation proceeds on the tracked `dev` branch.
- Added a minimal FastAPI application package with exactly pinned runtime
  dependencies.
- Added a minimal React/TypeScript/Vite application with exact dependency
  versions and a generated npm lockfile.
- Upgraded Vite to 6.4.3 after `npm audit` identified advisories in the original
  scaffold pin.
- Verified the production frontend build, zero npm audit findings, JSON manifest
  parsing, exact Python dependency pins, backend Python syntax, and ignored
  frontend build artifacts.
- No upload, database, object-storage, or authorization behavior was introduced.
- Next eligible story: R02.
