# Architecture Specification

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic, psycopg.
- Frontend: React, TypeScript, Vite, native `fetch`.
- Metadata: PostgreSQL in Docker.
- Object bytes: private MinIO bucket in Docker.
- Tests: pytest and FastAPI TestClient, with a fake storage adapter for API
  behavior and a live MinIO smoke flow for the completed stack.

The backend runs in Docker to pin the application runtime to Python 3.12
independently of the host setup. Containerizing the runtime also gives reviewers
a more reproducible setup.

## Service topology

```text
Browser :5173
  |-- metadata and authorization --> FastAPI :8000 --> PostgreSQL :5432
  |                                      |
  |                                      `--> MinIO internal endpoint minio:9000
  |
  `-- presigned PUT/GET file bytes -----------------> MinIO public endpoint localhost:9000

MinIO console: localhost:9001
```

The backend uses two MinIO clients with identical local development credentials:

- Internal client: `minio:9000` for bucket checks and object HEAD/stat calls.
- Public signing client: `localhost:9000` with a fixed region for URLs the host
  browser can resolve.

Never generate a URL for `minio:9000` and replace its hostname afterward. The
host participates in the signature.

## Data model

### companies

- `id UUID PRIMARY KEY`
- `name VARCHAR UNIQUE NOT NULL`

### users

- `id UUID PRIMARY KEY`
- `display_name VARCHAR NOT NULL`
- `company_id UUID NOT NULL REFERENCES companies(id)`

### uploads

- `id UUID PRIMARY KEY`
- `sample_id VARCHAR NOT NULL`
- `original_filename VARCHAR NOT NULL`
- `classification VARCHAR NOT NULL`
- `company_id UUID NOT NULL REFERENCES companies(id)` and indexed
- `object_key VARCHAR UNIQUE NOT NULL`
- `status upload_status NOT NULL`
- `content_type VARCHAR NOT NULL`
- `size_bytes BIGINT NULL`
- `etag VARCHAR NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- `updated_at TIMESTAMPTZ NOT NULL`

Object bytes never enter PostgreSQL. MinIO does not become the source of truth
for business ownership, classification, or processing state.

## Object key

```text
uploads/{company_uuid}/{upload_uuid}/{safe_filename}
```

The upload UUID and company UUID are generated or resolved by the backend. The
safe filename is derived from the submitted basename using a conservative
character allowlist and bounded length.

## API

```text
GET  /health
POST /api/uploads/initiate
POST /api/uploads/{upload_id}/confirm
GET  /api/uploads
GET  /api/uploads/{upload_id}
POST /api/uploads/{upload_id}/download-url
```

Public response models omit `object_key`. The browser needs the presigned URL,
not the storage address stored in the database.

## Upload sequence

1. Validate metadata and resolve `X-User-ID` to a seeded user and company.
2. Generate upload ID, sanitized filename, and company-scoped object key.
3. Create a `pending_upload` row and a five-minute presigned PUT URL.
4. Browser PUTs bytes directly to MinIO with the expected content type.
5. Browser confirms using only the upload ID.
6. Backend loads `WHERE id = :id AND company_id = :company_id`.
7. Backend obtains the object key from that row and performs `stat_object`.
8. Backend validates nonzero size and configured size limit and stores size/ETag.
9. Backend commits `uploaded` and launches the local simulated processor.
10. Processor uses a new database session and advances through queued,
    processing, and completed; exceptions produce failed.

## Download sequence

1. Resolve current user and company.
2. Load the upload with the same tenant-scoped query used by record retrieval.
3. If foreign or absent, return the identical 404 body.
4. Reject records that do not have a confirmed object.
5. Generate a one-minute GET URL using the row's object key.
6. Browser downloads directly from MinIO.

## Production processing path

Confirmation would commit `uploaded`, then publish an idempotent message
containing the upload ID to a durable queue. A worker would re-fetch the row,
transition it to processing, scan and process the object using a least-privilege
service identity, and mark completed or failed. Retries, dead-letter handling,
timeouts, and idempotency keys would replace the local background task.
