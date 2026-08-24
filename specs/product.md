# Product Specification

## Goal

Build a local full-stack application that uploads research images directly from
a browser to a private MinIO bucket while storing structured metadata in
PostgreSQL. The primary product invariant is strict isolation between Hospital A
and Hospital B.

## Development identities

- Dana belongs to Hospital A.
- David belongs to Hospital B.
- The UI may switch between seeded users.
- Requests identify the selected user with `X-User-ID`.
- The backend resolves that user to a company. The client never chooses its own
  company.

The header is a development authentication substitute, not a production login
design. Authorization remains mandatory on every backend route.

## Required user journeys

### Upload

1. Select a development user.
2. Enter sample ID and classification and choose an image.
3. Ask the backend to initiate an upload.
4. Receive a short-lived presigned PUT URL for a server-generated object key.
5. Upload file bytes directly from the browser to MinIO.
6. Confirm completion with the backend.
7. The backend verifies that the expected object exists and records its metadata.
8. Simulated processing advances through the required states.

### List and status

- A user sees only records owned by the user's company.
- The UI displays filename, sample ID, classification, created time, and status.
- The UI displays loading, empty, success, and failure states clearly.

### Download

1. Request a download for an accessible upload ID.
2. The backend performs tenant-scoped authorization first.
3. The backend returns a short-lived presigned GET URL.
4. The browser downloads directly from MinIO.

## Status lifecycle

```text
pending_upload -> uploaded -> queued -> processing -> completed
                                      \-> failed
```

`pending_upload` is an explicit additional state. A database record must exist
before the browser receives its upload URL, but it would be false to call that
record `uploaded` before MinIO confirms the object exists. All five assignment
states remain implemented.

## Validation

- `sample_id`: required, trimmed, bounded length.
- `classification`: required and chosen from a small documented demo taxonomy.
- `filename`: required, basename only, sanitized for the object key.
- `content_type`: allowlisted image MIME type.
- Unknown request fields are rejected, including `company_id` and `object_key`.
- Empty and oversized objects fail confirmation.

Client MIME types and file extensions are not proof of safe image contents.
Production processing must inspect magic bytes and perform malware/content
scanning in an isolated worker.

## Non-goals

- Full authentication, password management, or OIDC.
- A real AI/ML image model.
- A production message broker or distributed worker.
- Public bucket access or permanent file URLs.
- Advanced visual design.

## Definition of done

- A fresh clone starts using documented commands and example environment values.
- Hospital A can upload, confirm, list, process, and download its own image.
- Hospital B cannot list, retrieve, confirm, or obtain a download URL for that
  record and receives no existence-revealing metadata.
- Required automated tests pass.
- The bucket rejects anonymous list/read requests.
- The README covers every requested explanation and discloses AI assistance and
  human verification honestly.
