# Implementation Plan

This file is the human-readable Ralph plan. `ralph/prd.json` is the executable
story state. Product implementation has not started.

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
- [ ] R06: add tenant-scoped upload repository operations.

## Phase 3 - Private object storage and upload flow

- [ ] R07: add MinIO adapter and enforce a private bucket.
- [ ] R08: validate initiation metadata and generate safe object keys.
- [ ] R09: persist pending records and issue presigned PUT URLs.
- [ ] R10: confirm uploads using authorized rows and MinIO object stat.
- [ ] R11: simulate queued/processing/completed/failed transitions.

## Phase 4 - Access and download

- [ ] R12: expose tenant-scoped list and detail routes.
- [ ] R13: authorize and issue short-lived presigned GET URLs.
- [ ] R14: complete required and high-value security tests.

## Phase 5 - Browser experience

- [ ] R15: scaffold the typed React API client and development user switch.
- [ ] R16: implement direct browser-to-MinIO upload and confirmation.
- [ ] R17: implement accessible list, status polling, download, and feedback.

## Phase 6 - Integrated evidence and handoff

- [ ] R18: verify the live Hospital A success and Hospital B denial flows.
- [ ] Human Gate B: inspect the first full end-to-end flow.
- [ ] R19: write the complete README and AI verification disclosure.
- [ ] R20: perform final security review and clean-clone rehearsal.
- [ ] Human Gate C: approve push and submission.

## Global stop condition

Ralph stops only when every R01-R20 story passes, all required automated checks
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
