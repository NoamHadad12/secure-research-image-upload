# Security and Threat Specification

## Protected assets

- Research-image bytes.
- Sample ID, filename, classification, status, timestamps, and ownership.
- Object keys and presigned URLs.
- MinIO and PostgreSQL credentials.

## Trust boundaries

- Browser input is untrusted, including the selected development user header.
- FastAPI is the application authorization boundary.
- PostgreSQL is the ownership and metadata source of truth.
- MinIO accepts backend credentials or a narrowly scoped presigned request.
- A presigned URL is a temporary bearer capability and may be reused until it
  expires; it is not a user session or an authorization policy.

## Primary abuse cases and controls

### Guessing another upload ID

Control: every lookup includes both upload ID and current company ID. Foreign and
missing IDs produce the same status and response body.

### Supplying Hospital A as the company

Control: creation schemas forbid `company_id`. The backend derives the company
from a known seeded user.

### Selecting another object's storage key

Control: creation schemas forbid `object_key`; keys are generated server-side.
Confirm and download obtain the key only from an authorized row.

### Listing MinIO directly

Control: the bucket has no anonymous policy. The UI lists database rows through
a company-scoped backend route, never storage objects.

### Reusing or leaking a presigned URL

Controls: short expiry, operation-specific PUT/GET signature, unique key, no URL
logging, and generation only after authorization. Local upload expiry is five
minutes; local download expiry is one minute.

Known limitation: presigned URLs are not inherently one-time. During their
validity window, a holder can repeat the signed operation. Production options
include checksum-bound uploads, quarantine-to-final object promotion, versioning,
and stricter storage policies.

### Uploading non-image or malicious data

Controls in this assignment: MIME/extension allowlist, bounded metadata, maximum
size checked during confirmation, and failed status. Production must inspect
magic bytes and scan content in a sandboxed worker before treating it as safe.

### Metadata leakage through errors

Controls: generic foreign/missing 404 responses; no filename, company, object
key, or storage error included. Storage calls occur only after database
authorization succeeds.

### Secret leakage

Controls: `.env` and volumes ignored by Git; `.env.example` contains local
placeholders; frontend build variables contain no credentials; logs exclude
presigned query strings and secrets.

## Required negative evidence

- Hospital B's list excludes Hospital A rows.
- Hospital B gets the same 404 for Hospital A's ID and a random UUID.
- Hospital B cannot confirm Hospital A's object.
- Hospital B cannot obtain Hospital A's download URL.
- The storage adapter is not called after a failed authorization lookup.
- Client-provided `company_id` or `object_key` is rejected.
- Anonymous MinIO list/read attempts fail.

## Local-versus-production statement

The local backend may hold MinIO root credentials because the assignment is an
isolated development environment and explicitly prohibits exposing them to the
browser. Production must use separate least-privilege service identities,
rotated secrets, TLS, real authentication, audit logs, rate limits, and network
policies.
