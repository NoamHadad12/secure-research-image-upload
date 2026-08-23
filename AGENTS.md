# Secure Research Image Upload - Agent Guide

## Objective

Build the smallest complete application that proves company-level isolation for
research-image uploads. Correct authorization and a working browser-to-MinIO
flow matter more than feature count or visual polish.

## Ralph iteration contract

1. Read `specs/*`, `IMPLEMENTATION_PLAN.md`, `ralph/prd.json`, and
   `ralph/progress.md` before changing code.
2. Select exactly one highest-priority unblocked story whose dependencies pass.
3. Search the repository before assuming functionality is missing.
4. Implement only that story and its tests. Record unrelated discoveries in the
   plan instead of expanding scope.
5. Run the story's acceptance checks. Do not commit failing or unverified work.
6. When checks pass, update `ralph/prd.json`, `IMPLEMENTATION_PLAN.md`, and
   `ralph/progress.md`, then create the story's descriptive commit.
7. Stop after the one story. A new loop selects the next story with fresh focus.

After three unsuccessful iterations on the same failure, mark the story blocked,
record evidence and attempted fixes, and request human review.

## Non-negotiable security invariants

- Resolve the company from a server-side development user identity. Never trust
  a client-provided company ID.
- Scope every upload lookup by both upload ID and the authenticated company ID.
- Return the same `404 Upload not found` response for foreign and nonexistent
  upload IDs.
- Generate object keys on the backend. Never accept an object key from the
  browser.
- Keep the MinIO bucket private and never expose MinIO credentials to React.
- Authorize before generating any presigned upload or download URL.
- Read the object key from the authorized database record before accessing
  MinIO.
- Do not log presigned URLs, credentials, or sensitive query strings.
- Do not commit `.env`, credentials, generated uploads, or database volumes.

## Planned validation commands

Use the commands that exist at the current story. The completed project must
support:

```text
docker compose config
docker compose up --build -d
docker compose exec backend pytest
docker compose exec backend ruff check .
docker compose exec frontend npm run build
docker compose ps
```

Frontend stories also require browser verification. Security stories require
negative cross-company tests, not only successful owner flows.

## Human approval gates

- Gate A: approve specifications and story breakdown before product code.
- Gate B: manually verify the first complete Hospital A upload and Hospital B
  denial before documentation polish.
- Gate C: review the final diff, secret scan, README, and clean-clone run before
  push/submission.

Do not push, rewrite history, delete volumes, or perform destructive Git actions
without explicit user approval.
