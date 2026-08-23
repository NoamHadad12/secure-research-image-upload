# Ralph Progress Log

Append-only notes for future iterations. Task truth lives in `prd.json`; this
file records decisions and evidence that should survive a fresh context.

## 2026-08-23 - Planning baseline

- Repository started clean with one initial commit and only `README.md`.
- Chosen stack: Dockerized Python 3.12/FastAPI backend, React/TypeScript frontend,
  PostgreSQL metadata, private MinIO object storage.
- Local 64-bit Python 3.12 and 3.13 are available. Docker still pins the
  backend to Python 3.12 and makes reviewer setup reproducible.
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

## 2026-08-23 - R02 local Docker Compose infrastructure

- Added `docker-compose.yml` for PostgreSQL 17, private MinIO, FastAPI, and
  React/Vite with named volumes for database and object-storage data.
- Added Dockerfiles and Docker ignore files so each application service builds
  reproducibly from its committed dependency manifest.
- Added `.env.example` with development-only placeholders. The browser-facing
  frontend receives only its API URL; no MinIO or database credential is exposed
  to it.
- Added root ignore rules for local environment files, runtime data, build
  outputs, caches, and editor-local settings.
- Configured MinIO global CORS for the configured frontend origin only. Live
  preflight verification allowed `http://localhost:5173` and denied
  `http://evil.example`.
- Verified `docker compose config`, `docker compose up --build -d`, healthy
  PostgreSQL, running backend/frontend/MinIO services, frontend HTTP 200, and
  MinIO health HTTP 200.
- Next eligible story: R03.

## 2026-08-23 - R03 backend configuration and health boundary

- Added Pydantic settings with validation and normalization for
  `FRONTEND_ORIGIN`; CORS consumes only that validated origin.
- Added an application factory so tests inject explicit settings instead of
  depending on process-global state.
- Added narrow CORS rules: only GET/POST, Content-Type/X-User-ID headers, no
  credentialed cross-origin requests, and no wildcard origin.
- Added stable `GET /health` response and a single safe error envelope for
  validation, HTTP, and unexpected errors.
- Added focused tests for settings validation, health, allowed/denied CORS, and
  generic 404 responses.
- Updated the backend image to include tests and set `PYTHONPATH=/app`, so the
  documented `docker compose exec backend pytest` command runs successfully.
- Verified Docker rebuild/container startup, seven pytest tests, Ruff, and live
  HTTP health, CORS, and safe-error responses.
- Next eligible story: R04.

## 2026-08-23 - R04 metadata schema and initial migration

- Added SQLAlchemy models for companies, users, and upload metadata. Image bytes
  remain outside PostgreSQL in MinIO.
- Added UUID primary keys and company foreign keys with `RESTRICT` deletion
  behavior. Upload company IDs and development user company IDs are indexed.
- Added the `upload_status` PostgreSQL enum with `pending_upload`, `uploaded`,
  `queued`, `processing`, `completed`, and `failed`.
- Enforced a unique upload object key, database-initialized timestamps, and ORM
  timestamp refresh behavior in the model metadata and initial Alembic migration.
- Added Alembic configuration that obtains `DATABASE_URL` only from the runtime
  environment and fails clearly if it is absent.
- Verified ten pytest tests and Ruff. Applied the migration to a fresh local
  PostgreSQL schema, verified the head revision, tables, enum values, company
  index, and object-key unique constraint, then reran the upgrade idempotently.
- Next eligible story: R05.

## 2026-08-23 - R02-R04 quality audit

- Rebuilt the backend and revalidated the complete R02-R04 baseline: ten pytest
  tests, Ruff, `alembic check`, production React build, and all Compose services.
- Detected and corrected a model/migration type drift before it could reach a
  later migration: `uploads.size_bytes` now explicitly uses PostgreSQL
  `BIGINT` in both places. A model test protects this contract.
- Clarified timestamp documentation so it accurately distinguishes database
  initialization from SQLAlchemy's update-time SQL expression.

## 2026-08-23 - R05 development identities and tenant context

- Added deterministic development identities: Alice at Hospital A and Bob at
  Hospital B. The backend seeds them after migrations at startup; a second seed
  run preserves exactly two companies and two users.
- Added a request dependency that resolves `X-User-ID` to the database user and
  its company. It does not read a client-supplied company ID or any other tenant
  hint.
- Missing, malformed, and unknown development user IDs all return the same
  generic 401 response.
- Added isolated identity tests using an in-memory database, including a forged
  `X-Company-ID` header that cannot change Alice's resolved Hospital A tenant.
- Verified 15 pytest tests, Ruff, Alembic model/migration consistency, and a
  live Compose startup with Alice and Bob present in PostgreSQL.
- Next eligible story: R06.

## 2026-08-23 - R04 PostgreSQL enum regression correction

- Corrected the SQLAlchemy upload-status enum mapping to persist enum `.value`
  strings such as `pending_upload`, matching the existing PostgreSQL enum
  created by the initial migration.
- Enabled string validation and added a live PostgreSQL regression test that
  inserts a pending upload, verifies the stored lowercase enum value, and rolls
  the test transaction back.
- Verified 16 pytest tests, Ruff, and Alembic model/migration consistency.
- Next eligible story remains R06.
