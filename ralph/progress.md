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
