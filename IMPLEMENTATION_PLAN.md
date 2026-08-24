# Implementation Plan

This file is the human-readable Ralph plan. `ralph/prd.json` is the executable
story state. Product implementation is in progress on the tracked `dev` branch.

## Phase 0 - Planning gate

- [x] Analyze the assignment and repository state.
- [x] Define product flow, architecture, security invariants, and stop condition.
- [x] Split the build into atomic stories with acceptance criteria.
- [x] Human Gate A: review and approve this plan before product code.

## Phase 1 - Reproducible foundation

- [x] R01: scaffold backend and frontend workspaces.
- [x] R02: add environment contract, ignore rules, and Compose infrastructure.
- [x] R03: add FastAPI configuration, error shape, CORS, and health endpoint.

## Phase 2 - Metadata and identity

- [x] R04: add SQLAlchemy upload/identity models and initial migration.
- [x] R05: seed Hospital A/B users and resolve `X-User-ID` server-side.
- [x] R06: add tenant-scoped upload repository operations.

## Phase 3 - Private object storage and upload flow

- [x] R07: add MinIO adapter and enforce a private bucket.
- [x] R08: validate initiation metadata and generate safe object keys.
- [x] R09: persist pending records and issue presigned PUT URLs.
- [x] R10: confirm uploads using authorized rows and MinIO object stat.
- [x] R11: simulate queued/processing/completed/failed transitions.
  - The local in-process task is intentionally non-durable; R19 must document
    that production needs a queue, worker, retries, and dead-letter handling.

## Phase 4 - Access and download

- [x] R12: expose tenant-scoped list and detail routes.
- [x] R13: authorize and issue short-lived presigned GET URLs.
- [x] R14: complete required and high-value security tests.

## Phase 5 - Browser experience

- [x] R15: scaffold the typed React API client and development user switch.
- [x] R16: implement direct browser-to-MinIO upload and confirmation.
- [x] R17: implement accessible list, status polling, download, and feedback.

## Phase 6 - Integrated evidence and handoff

- [x] R18: verify the live Hospital A success and Hospital B denial flows.
- [x] Human Gate B: inspect the first full end-to-end flow.
- [x] R19: write the complete README and AI verification disclosure.
  - Include a maintained data-model diagram derived from the final PostgreSQL
    schema, showing that image bytes remain in MinIO rather than the database.
- [x] R20: perform final security review and clean-clone rehearsal.
- [x] Human Gate C: approve the final diff and submission readiness.

## Phase 7 - Post-review UX correction

- [x] R21: stabilize background status polling and remove browser-shell noise.
  - Keep abandoned `pending_upload` records visible without polling forever.
  - Refresh processing statuses silently without flashing the blocking loading UI.
  - Serve an explicit local favicon so the browser console remains clean.

## Phase 8 - Lightweight presentation polish

- [x] R22: improve the frontend hierarchy and rename the development identities.
  - Keep the existing upload and tenant-isolation behavior unchanged.
  - Rename the stable Hospital A/B identities to Dana and David consistently.
  - Keep the interface responsive, accessible, and intentionally lightweight.

## Phase 9 - README accuracy review

- [x] R23: tighten README accuracy and secret-safe validation guidance.
  - Validate Compose configuration without printing resolved credentials.
  - Describe the persisted sanitized filename and exact generic 404 body.
  - Distinguish automated checks from browser and negative security checks.
  - Separate the historical 57-test milestones from the current 58-test suite.

## Global stop condition

Ralph stops only when every R01-R23 story passes, all required automated checks
are green, the live cross-company scenario is verified, the README covers all 13
requested topics, and a clean clone can be run from documented commands.

## Scope fallback order

If the deadline becomes tight, remove optional work in this order:

1. Screen recording.
2. CI workflow.
3. Additional visual polish.
4. Extra integration automation beyond the required tests.

Never remove server-side tenant isolation, direct presigned upload, confirmation
via object existence check, authorized download, required tests, or README
coverage.
