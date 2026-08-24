import { type FormEvent, useEffect, useState } from "react";

import { ApiError, createApiClient } from "./api";
import type { DevelopmentUser, UploadRecord } from "./types";

const developmentUsers: readonly DevelopmentUser[] = [
  {
    id: "00000000-0000-0000-0000-0000000000a2",
    name: "Alice",
    companyName: "Hospital A",
  },
  {
    id: "00000000-0000-0000-0000-0000000000b2",
    name: "Bob",
    companyName: "Hospital B",
  },
];

const classifications = ["research", "clinical", "restricted"] as const;
const acceptedContentTypes = new Set(["image/png", "image/jpeg", "image/webp"]);
const activeUploadStatuses = new Set(["pending_upload", "uploaded", "queued", "processing"]);
const pollingIntervalMilliseconds = 2_000;

type RecordLoadState =
  | { kind: "loading" }
  | { kind: "ready" }
  | { kind: "error"; message: string };

type UploadState =
  | { kind: "idle" }
  | { kind: "initiating" }
  | { kind: "uploading" }
  | { kind: "confirming" }
  | { kind: "success"; status: string }
  | { kind: "error"; message: string };

type DownloadState =
  | { kind: "idle" }
  | { kind: "requesting"; uploadId: string }
  | { kind: "success"; filename: string }
  | { kind: "error"; message: string };

function formatCreatedAt(value: string): string {
  const createdAt = new Date(value);
  if (Number.isNaN(createdAt.getTime())) {
    return "Unavailable";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(createdAt);
}

export function App() {
  const [selectedUser, setSelectedUser] = useState<DevelopmentUser>(developmentUsers[0]);
  const [records, setRecords] = useState<UploadRecord[]>([]);
  const [recordLoadState, setRecordLoadState] = useState<RecordLoadState>({ kind: "loading" });
  const [recordRefreshVersion, setRecordRefreshVersion] = useState(0);
  const [sampleId, setSampleId] = useState("");
  const [classification, setClassification] = useState<(typeof classifications)[number]>("research");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [uploadState, setUploadState] = useState<UploadState>({ kind: "idle" });
  const [downloadState, setDownloadState] = useState<DownloadState>({ kind: "idle" });

  useEffect(() => {
    const controller = new AbortController();
    let isCurrentRequest = true;

    void createApiClient(selectedUser.id)
      .listUploads(controller.signal)
      .then((loadedRecords) => {
        if (!isCurrentRequest) {
          return;
        }
        setRecords(loadedRecords);
        setRecordLoadState({ kind: "ready" });
      })
      .catch((error: unknown) => {
        if (!isCurrentRequest || (error instanceof DOMException && error.name === "AbortError")) {
          return;
        }
        setRecords([]);
        setRecordLoadState({
          kind: "error",
          message: error instanceof ApiError ? error.message : "Request could not be completed",
        });
      });

    return () => {
      isCurrentRequest = false;
      controller.abort();
    };
  }, [recordRefreshVersion, selectedUser.id]);

  const hasActiveUploads = records.some((record) => activeUploadStatuses.has(record.status));

  useEffect(() => {
    if (!hasActiveUploads) {
      return;
    }

    const timer = window.setTimeout(() => {
      setRecordLoadState({ kind: "loading" });
      setRecordRefreshVersion((version) => version + 1);
    }, pollingIntervalMilliseconds);
    return () => window.clearTimeout(timer);
  }, [hasActiveUploads, records]);

  const uploadInProgress = ["initiating", "uploading", "confirming"].includes(uploadState.kind);
  const downloadInProgress = downloadState.kind === "requesting";
  const userSwitchDisabled = uploadInProgress || downloadInProgress;

  function refreshRecords(clearRecords = true): void {
    if (clearRecords) {
      setRecords([]);
    }
    setRecordLoadState({ kind: "loading" });
    setRecordRefreshVersion((version) => version + 1);
  }

  function selectUser(user: DevelopmentUser): void {
    if (user.id === selectedUser.id || userSwitchDisabled) {
      return;
    }

    // Clear the old tenant's data before the new tenant's request can resolve.
    setRecords([]);
    setRecordLoadState({ kind: "loading" });
    setUploadState({ kind: "idle" });
    setDownloadState({ kind: "idle" });
    setSelectedUser(user);
  }

  async function submitUpload(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    const file = selectedFile;
    if (file === null) {
      setUploadState({ kind: "error", message: "Choose an image before uploading." });
      return;
    }
    if (!acceptedContentTypes.has(file.type)) {
      setUploadState({
        kind: "error",
        message: "Choose a PNG, JPEG, or WebP image with a recognized MIME type.",
      });
      return;
    }

    const client = createApiClient(selectedUser.id);
    try {
      setUploadState({ kind: "initiating" });
      const initiatedUpload = await client.initiateUpload({
        sample_id: sampleId,
        filename: file.name,
        classification,
        content_type: file.type,
      });

      setUploadState({ kind: "uploading" });
      const storageResponse = await fetch(initiatedUpload.upload_url, {
        body: file,
        headers: { "Content-Type": file.type },
        method: "PUT",
      });
      if (!storageResponse.ok) {
        throw new Error("Storage upload failed");
      }

      setUploadState({ kind: "confirming" });
      const confirmation = await client.confirmUpload(initiatedUpload.upload_id);
      setSampleId("");
      setSelectedFile(null);
      setFileInputKey((key) => key + 1);
      setUploadState({ kind: "success", status: confirmation.status });
      refreshRecords();
    } catch (error: unknown) {
      setUploadState({
        kind: "error",
        message:
          error instanceof ApiError
            ? error.message
            : "Could not complete the upload. Verify the image and try again.",
      });
    }
  }

  async function downloadUpload(record: UploadRecord): Promise<void> {
    try {
      setDownloadState({ kind: "requesting", uploadId: record.upload_id });
      const download = await createApiClient(selectedUser.id).createDownloadUrl(record.upload_id);

      // The backend authorized and signed this temporary URL. Do not retain or log it.
      const link = document.createElement("a");
      link.href = download.download_url;
      link.download = record.filename;
      document.body.append(link);
      link.click();
      link.remove();

      setDownloadState({ kind: "success", filename: record.filename });
    } catch (error: unknown) {
      setDownloadState({
        kind: "error",
        message:
          error instanceof ApiError
            ? error.message
            : "Could not start the download. Please try again.",
      });
    }
  }

  return (
    <main>
      <h1>Secure Research Image Uploads</h1>
      <p>
        Development identity: <strong>{selectedUser.name}</strong> ({selectedUser.companyName})
      </p>

      <fieldset disabled={userSwitchDisabled}>
        <legend>Switch development user</legend>
        {developmentUsers.map((user) => (
          <label key={user.id}>
            <input
              checked={selectedUser.id === user.id}
              name="development-user"
              onChange={() => selectUser(user)}
              type="radio"
              value={user.id}
            />
            {user.name} — {user.companyName}
          </label>
        ))}
      </fieldset>

      <section aria-labelledby="upload-heading">
        <h2 id="upload-heading">Upload an image</h2>
        <form onSubmit={submitUpload}>
          <p>
            <label>
              Sample ID
              <input
                disabled={uploadInProgress}
                onChange={(event) => setSampleId(event.target.value)}
                required
                value={sampleId}
              />
            </label>
          </p>
          <p>
            <label>
              Classification
              <select
                disabled={uploadInProgress}
                onChange={(event) =>
                  setClassification(event.target.value as (typeof classifications)[number])
                }
                value={classification}
              >
                {classifications.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          </p>
          <p>
            <label>
              Image file
              <input
                accept="image/png,image/jpeg,image/webp"
                disabled={uploadInProgress}
                key={fileInputKey}
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                required
                type="file"
              />
            </label>
          </p>
          <button disabled={uploadInProgress} type="submit">
            {uploadInProgress ? "Uploading…" : "Upload image"}
          </button>
        </form>

        <section aria-atomic="true" aria-live="polite">
          {uploadState.kind === "initiating" && <p>Preparing a secure upload…</p>}
          {uploadState.kind === "uploading" && <p>Uploading image directly to private storage…</p>}
          {uploadState.kind === "confirming" && <p>Confirming the stored image…</p>}
          {uploadState.kind === "success" && (
            <p>Image uploaded and confirmed. Current status: {uploadState.status}.</p>
          )}
          {uploadState.kind === "error" && <p role="alert">{uploadState.message}</p>}
        </section>
      </section>

      <section aria-labelledby="records-heading">
        <h2 id="records-heading">Accessible uploads</h2>
        <button disabled={recordLoadState.kind === "loading"} onClick={() => refreshRecords()} type="button">
          Refresh records
        </button>

        <section aria-atomic="true" aria-live="polite">
          {recordLoadState.kind === "loading" && <p>Refreshing accessible upload records…</p>}
          {recordLoadState.kind === "error" && (
            <p role="alert">Could not refresh accessible records: {recordLoadState.message}</p>
          )}
          {recordLoadState.kind === "ready" && records.length === 0 && (
            <p>No uploads are accessible for this development user.</p>
          )}
        </section>

        {records.length > 0 && (
          <ul aria-label="Accessible upload records">
            {records.map((record) => (
              <li key={record.upload_id}>
                <h3>{record.filename}</h3>
                <dl>
                  <div>
                    <dt>Sample ID</dt>
                    <dd>{record.sample_id}</dd>
                  </div>
                  <div>
                    <dt>Classification</dt>
                    <dd>{record.classification}</dd>
                  </div>
                  <div>
                    <dt>Status</dt>
                    <dd>{record.status}</dd>
                  </div>
                  <div>
                    <dt>Created</dt>
                    <dd>
                      <time dateTime={record.created_at}>{formatCreatedAt(record.created_at)}</time>
                    </dd>
                  </div>
                </dl>
                <button
                  disabled={downloadInProgress || record.status === "pending_upload"}
                  onClick={() => void downloadUpload(record)}
                  type="button"
                >
                  {downloadState.kind === "requesting" &&
                  downloadState.uploadId === record.upload_id
                    ? "Preparing download…"
                    : "Download"}
                </button>
                {record.status === "pending_upload" && (
                  <p>Download is available after the image is confirmed.</p>
                )}
              </li>
            ))}
          </ul>
        )}

        <section aria-atomic="true" aria-live="polite">
          {downloadState.kind === "success" && <p>Download started for {downloadState.filename}.</p>}
          {downloadState.kind === "error" && <p role="alert">{downloadState.message}</p>}
        </section>
      </section>
    </main>
  );
}
