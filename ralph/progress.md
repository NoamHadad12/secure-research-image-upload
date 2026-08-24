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

## 2026-08-23 - Documentation decision

- R19 must include a maintained data-model diagram derived from the final schema.
  It will show `companies`, `users`, and `uploads`, while making clear that image
  bytes are stored privately in MinIO and only the object key is in PostgreSQL.

## 2026-08-23 - R06 tenant-scoped upload repository

- Added a dedicated upload repository with explicit SQL filters for company-scoped
  list and detail reads. The detail lookup includes both `upload_id` and
  `company_id` in the same query.
- Foreign and nonexistent upload IDs both return `None`; later API routes will
  map that shared outcome to the same safe `404 Upload not found` response.
- Added a flush-only metadata persistence helper. The caller owns commit or
  rollback so later upload initiation and confirmation flows can stay atomic.
- Added repository isolation tests for owner reads, cross-company list isolation,
  foreign/nonexistent equivalence, and non-committing persistence.
- Verified the focused repository suite (4 tests), full backend suite (20 tests),
  and Ruff in the rebuilt Docker backend.
- Next eligible story: R07.

## 2026-08-23 - R07 private MinIO storage adapter

- Added a backend-only MinIO adapter with distinct internal (`minio:9000`) and
  browser-facing signing (`localhost:9000`) clients. The future presigner will
  use the latter directly rather than rewrite an already-signed URL.
- Backend startup now idempotently creates the configured bucket and removes an
  existing bucket policy. No MinIO credential is stored in a public schema or
  sent to the frontend.
- Added endpoint validation, secret-aware settings, and a replaceable storage
  protocol so tests can use a fake without contacting MinIO.
- Verified 3 focused storage tests, 23 backend tests, and Ruff in the rebuilt
  Docker stack. The live `research-images` bucket exists and an anonymous
  request returned `403 AccessDenied`.
- Next eligible story: R08.

## 2026-08-23 - R08 upload-initiation metadata validation and object keys

- Added a strict, route-independent Pydantic model for the metadata that will
  later be accepted by upload initiation. It requires a trimmed bounded sample
  ID, one of the documented demo classifications (`research`, `clinical`, or
  `restricted`), and PNG/JPEG/WebP MIME types only.
- Unknown input fields, including client-supplied `company_id` and `object_key`,
  are forbidden before persistence or storage access.
- Filenames are reduced to a conservative ASCII basename with a MIME-matching
  extension and a bounded length. The backend-only key builder creates exactly
  `uploads/{company_uuid}/{upload_uuid}/{safe_filename}` and refuses filename
  path separators.
- Added focused validation and key-layout tests. No route, database write, or
  presigned URL was added; those belong to R09.
- Next eligible story: R09.

## 2026-08-23 - R09 presigned upload initiation

- Added `POST /api/uploads/initiate`. It resolves the company exclusively from
  the authenticated development user, creates a UUID and server-generated
  object key, flushes a `pending_upload` record, then returns only after the
  database transaction commits.
- The private storage adapter now signs a five-minute PUT URL through its
  browser-reachable MinIO client. No signed URL is rewritten, logged, or paired
  with MinIO credentials in the public response.
- The response includes only the upload ID, temporary URL, and 300-second
  expiry; it deliberately omits object key and company metadata.
- Added API and adapter tests for Hospital A ownership, forged metadata
  rejection before storage/persistence, the pending state, expiry, and use of
  the browser-facing signing client. Confirmation remains R10.
- Next eligible story: R10.

## 2026-08-23 - R10 authorized object confirmation

- Added `POST /api/uploads/{upload_id}/confirm`. It performs the tenant-scoped
  database lookup before any storage operation, obtains the object key only
  from the authorized row, and returns the same `404 Upload not found` error
  for foreign and nonexistent upload IDs.
- The backend now stats the object through the Docker-internal MinIO client.
  Missing, empty, and oversized objects remain pending and return a generic
  conflict response; valid objects persist their size and ETag then transition
  to `uploaded`. Repeated confirmation of an uploaded record is idempotent.
- Added a configurable 10 MiB upload limit (`MAX_UPLOAD_BYTES`) and a public
  confirmation response that omits the object key.
- Confirmation coverage uses the running PostgreSQL service with cleanup of
  each generated test row. A fake storage adapter proves authorization precedes
  storage and avoids real MinIO bytes until R18.
- Next eligible story: R11.

## 2026-08-24 - R11 local processing lifecycle

- Confirmation now schedules an in-process FastAPI background task only after
  the `uploaded` transaction commits. The task receives an upload ID and opens
  its own PostgreSQL session; it never reuses the request session.
- The simulator commits `queued`, `processing`, and `completed` transitions.
  A processor exception rolls back its failed operation then records `failed`.
- PostgreSQL-backed tests verify every transition, independent background
  session creation, and the failure path. The existing confirmation test now
  verifies that confirmation starts this background lifecycle.
- This local task is deliberately non-durable. Production requires a queue,
  separate worker, idempotency, retries, timeouts, and dead-letter handling;
  the R19 README must describe that limitation.
- Next eligible story: R12.

## 2026-08-24 - R12 tenant-scoped upload access routes

- Added `GET /api/uploads` and `GET /api/uploads/{upload_id}`. Both resolve the
  current user server-side and pass only that user's company ID into the
  repository's SQL-scoped reads.
- Public record responses include the required user-facing metadata (upload ID,
  sample ID, filename, classification, status, and created timestamp) while
  omitting the object key, company ID, ETag, size, and all storage details.
- Foreign and nonexistent detail IDs both return the same generic `404 Upload
  not found` response; Hospital B's list contains only Hospital B records.
- Added API coverage for Hospital A owner list/detail success, Hospital B list
  isolation, and foreign/nonexistent error equivalence.
- Verified `docker compose config`, `docker compose up --build -d`, full backend
  `pytest` (45 passed), `ruff check .`, frontend `npm run build`, and healthy
  Compose services.
- Next eligible story: R13.

## 2026-08-24 - R13 authorized presigned download URLs

- Added `POST /api/uploads/{upload_id}/download-url`. It resolves the current
  user server-side and authorizes the upload with the same tenant-scoped query
  used by detail retrieval before invoking any storage adapter method.
- Only uploads beyond `pending_upload` can receive a URL. The public response
  contains the upload ID, temporary GET URL, and a 60-second expiry; it never
  exposes the object key or MinIO credentials.
- The MinIO adapter now signs GET URLs with its browser-reachable client, never
  by rewriting an internal signed URL.
- Added owner, foreign/nonexistent equivalence, pending-record, and signing
  client tests. Denied and pending requests prove no GET URL is signed.
- Verified `docker compose up --build -d`, full backend `pytest` (49 passed),
  `ruff check .`, frontend `npm run build`, and healthy Compose services.
- Next eligible story: R14.

## 2026-08-24 - R14 API security regression suite

- Added a dedicated assignment-regression suite with explicit, clearly named
  tests for all four required scenarios: Hospital A creation and access,
  Hospital B record denial, Hospital B download-URL denial, and invalid or
  missing initiation metadata rejection.
- The suite asserts that Hospital B's foreign and random IDs return the exact
  same 404 response, and that a denied download request never calls the GET
  presigner.
- Metadata validation coverage now explicitly rejects client attempts to supply
  `company_id`, `object_key`, or both, without persisting a row or generating a
  PUT URL.
- Verified `docker compose up --build -d`, full backend `pytest` (57 passed),
  `ruff check .`, frontend `npm run build`, and healthy Compose services.
- Next eligible story: R15.

## 2026-08-24 - R15 typed frontend API client and development user switch

- Added a typed frontend API client that binds every request to the selected
  development user's `X-User-ID`; it never sends a company ID or storage key.
- Added an accessible Alice/Hospital A and Bob/Hospital B radio switch. Switching
  immediately clears the prior tenant's in-memory records, cancels an outdated
  request, and refreshes records for the newly selected user.
- Verified the TypeScript/Vite production build and browser behavior: Alice
  showed six accessible records, Bob showed zero, and switching back restored
  Alice's six-record result without stale Hospital A data while Bob was active.
- Next eligible story: R16.

## 2026-08-24 - R16 direct browser upload and confirmation

- Added a controlled upload form for sample ID, classification, and an allowlisted
  PNG/JPEG/WebP image. It sends only metadata to the backend and never exposes
  object keys or storage credentials in the UI.
- The browser requests a short-lived PUT URL, uploads image bytes directly to
  MinIO with the file MIME type, then confirms the upload using only its upload
  ID. Errors leave form values available for a retry and use safe feedback.
- Verified the production frontend build and a live browser flow with a temporary
  non-sensitive PNG: Alice's accessible-record count advanced from six to seven
  after MinIO upload and backend confirmation returned `uploaded`.
- Verified initiation-error feedback with a whitespace sample ID: the backend
  rejected the request before signing, the UI displayed `Request validation failed`,
  and the upload button remained enabled for retry.
- Next eligible story: R17.

## 2026-08-24 - R17 upload list, status polling, and downloads

- Added an accessible list that exposes only public upload metadata: filename,
  sample ID, classification, status, and created time. Pending uploads explain
  why download is unavailable rather than attempting an ineligible request.
- Added a manual refresh control and two-second status polling only while a
  visible record is pending, uploaded, queued, or processing; polling stops as
  soon as no active status remains.
- Each Download click asks the backend for a fresh authorized URL and starts a
  direct browser download without retaining or logging that temporary URL.
- Verified the production frontend build and browser states: Alice saw her
  records and downloaded a confirmed image; Bob saw the accessible-empty state
  with none of Alice's record metadata.
- Next eligible story: R18.

## 2026-08-24 - R18 live MinIO tenant-isolation flow

- Used the real browser UI as Alice/Hospital A to upload the non-sensitive
  `r18-live-smoke.png` fixture (2,082,509 bytes, SHA-256
  `246623C14C589757FEC414AECD254C53233397FC76A27F31D5CCCD2B059E95BC`) with
  sample ID `r18-live-smoke-20260824` and classification `restricted`.
- The browser completed the presigned PUT and confirmation, displayed the
  `uploaded` response, then visibly showed `processing` and `completed`. A
  browser download event was observed for the completed record. A second owner
  download contained 2,082,509 bytes and matched the fixture SHA-256 exactly.
- The created upload ID was `0d0dce5e-bb89-4223-8ab1-be9d795b1b68`. Switching
  the UI to Bob/Hospital B cleared Alice's metadata and showed the accessible
  empty state. Bob's API list contained zero records and no matching upload or
  sample metadata.
- Bob's detail, confirmation, and download-URL requests for Alice's upload all
  returned `404` with exactly
  `{"error":{"code":"not_found","message":"Upload not found"}}`. A random
  UUID returned the same detail status and body.
- Anonymous MinIO bucket listing and a direct unsigned GET for the exact object
  path both returned `403`; no bucket policy, object bytes, or metadata leaked.
- Exact terminal checks used after the browser flow:

  ```powershell
  $bobHeaders = @{"X-User-ID" = "00000000-0000-0000-0000-0000000000b2"}
  $uploadId = "0d0dce5e-bb89-4223-8ab1-be9d795b1b68"
  Invoke-WebRequest -SkipHttpErrorCheck -Uri "http://localhost:8000/api/uploads/$uploadId" -Headers $bobHeaders
  Invoke-WebRequest -SkipHttpErrorCheck -Method Post -Uri "http://localhost:8000/api/uploads/$uploadId/confirm" -Headers $bobHeaders
  Invoke-WebRequest -SkipHttpErrorCheck -Method Post -Uri "http://localhost:8000/api/uploads/$uploadId/download-url" -Headers $bobHeaders
  Invoke-WebRequest -SkipHttpErrorCheck -Uri "http://localhost:9000/research-images?list-type=2"
  Invoke-WebRequest -SkipHttpErrorCheck -Uri "http://localhost:9000/research-images/uploads/00000000-0000-0000-0000-0000000000a1/$uploadId/r18-live-smoke.png"
  docker compose config
  docker compose exec backend pytest
  docker compose exec backend ruff check .
  docker compose exec frontend npm run build
  docker compose ps
  ```

- Final checks passed: 57 backend tests, Ruff, the production frontend build,
  valid Compose configuration, and all four services running with PostgreSQL
  healthy. No product-code change was needed for R18.
- Next step: Human Gate B. R19 remains blocked on that manual approval.

## 2026-08-24 - Human Gate B and R19 complete assignment README

- The user approved the R18 evidence and commit, then explicitly instructed the
  work to continue to the next subtask. This records Human Gate B as approved.
- Replaced the placeholder README with an English assignment handoff. Each of
  the 13 requested documentation topics maps to its own numbered heading.
- Added a Mermaid data-model diagram derived from the final PostgreSQL schema.
  It distinguishes the three database tables from the MinIO object that holds
  the actual image bytes.
- Documented the exact setup and validation commands, development identities,
  API surface, metadata validation, upload and download authorization flows,
  5-minute PUT and 1-minute GET expiry choices, and private-bucket behavior.
- Documented honest boundaries: the forgeable development identity header,
  bearer and reusable-until-expiry nature of presigned URLs, local MinIO root
  credentials, non-durable FastAPI background processing, and abandoned
  `pending_upload` cleanup as production work.
- Disclosed OpenAI Codex with GPT-5, what it assisted with, what local evidence
  was reviewed, and that the final clean-clone and history/secret audit remains
  a separate R20 gate.
- Reran the commands exactly as documented: `docker compose config`,
  `docker compose up --build -d`, backend `pytest` (57 passed), backend
  `ruff check .`, frontend `npm run build`, the documented backend import check,
  and `docker compose ps`. All passed and all services were running; PostgreSQL
  was healthy.
- Next eligible story: R20 final security review and clean-clone rehearsal.
