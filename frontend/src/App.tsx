import { type FormEvent, useEffect, useState } from "react";

import { ApiError, createApiClient } from "./api";
import "./App.css";
import type { DevelopmentUser, UploadRecord } from "./types";

const developmentUsers: readonly DevelopmentUser[] = [
  {
    id: "00000000-0000-0000-0000-0000000000a2",
    name: "Dana",
    companyName: "Hospital A",
  },
  {
    id: "00000000-0000-0000-0000-0000000000b2",
    name: "David",
    companyName: "Hospital B",
  },
];

const classifications = ["research", "clinical", "restricted"] as const;
const acceptedContentTypes = new Set(["image/png", "image/jpeg", "image/webp"]);
const pollingUploadStatuses = new Set(["uploaded", "queued", "processing"]);
const pollingIntervalMilliseconds = 2_000;

type RecordLoadState =
  | { kind: "loading" }
  | { kind: "ready" }
  | { kind: "error"; message: string };

type RecordRefreshRequest = {
  sequence: number;
  background: boolean;
};

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

function formatStatus(value: string): string {
  return value.split("_").join(" ");
}

export function App() {
  const [selectedUser, setSelectedUser] = useState<DevelopmentUser>(developmentUsers[0]);
  const [records, setRecords] = useState<UploadRecord[]>([]);
  const [recordLoadState, setRecordLoadState] = useState<RecordLoadState>({ kind: "loading" });
  const [recordRefreshRequest, setRecordRefreshRequest] = useState<RecordRefreshRequest>({
    sequence: 0,
    background: false,
  });
  const [backgroundRefreshError, setBackgroundRefreshError] = useState<string | null>(null);
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
        setBackgroundRefreshError(null);
      })
      .catch((error: unknown) => {
        if (!isCurrentRequest || (error instanceof DOMException && error.name === "AbortError")) {
          return;
        }

        if (recordRefreshRequest.background) {
          setBackgroundRefreshError(
            error instanceof ApiError
              ? `Could not refresh status updates: ${error.message}`
              : "Could not refresh status updates. Use Refresh records to try again.",
          );
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
  }, [recordRefreshRequest, selectedUser.id]);

  const hasPollingUploads = records.some((record) => pollingUploadStatuses.has(record.status));

  useEffect(() => {
    if (!hasPollingUploads) {
      return;
    }

    const timer = window.setTimeout(() => {
      setRecordRefreshRequest((request) => ({
        sequence: request.sequence + 1,
        background: true,
      }));
    }, pollingIntervalMilliseconds);
    return () => window.clearTimeout(timer);
  }, [hasPollingUploads, records]);

  const uploadInProgress = ["initiating", "uploading", "confirming"].includes(uploadState.kind);
  const downloadInProgress = downloadState.kind === "requesting";
  const userSwitchDisabled = uploadInProgress || downloadInProgress;

  function refreshRecords(clearRecords = true): void {
    if (clearRecords) {
      setRecords([]);
    }
    setBackgroundRefreshError(null);
    setRecordLoadState({ kind: "loading" });
    setRecordRefreshRequest((request) => ({
      sequence: request.sequence + 1,
      background: false,
    }));
  }

  function selectUser(user: DevelopmentUser): void {
    if (user.id === selectedUser.id || userSwitchDisabled) {
      return;
    }

    // Clear the old tenant's data before the new tenant's request can resolve.
    setRecords([]);
    setRecordLoadState({ kind: "loading" });
    setBackgroundRefreshError(null);
    setUploadState({ kind: "idle" });
    setDownloadState({ kind: "idle" });
    setRecordRefreshRequest((request) => ({
      sequence: request.sequence + 1,
      background: false,
    }));
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
    <main className="app-shell">
      <header className="hero">
        <div className="brand-mark" aria-hidden="true">SR</div>
        <div className="hero__copy">
          <p className="eyebrow">Private research storage</p>
          <h1>Secure Research Image Uploads</h1>
          <p className="hero__description">
            Upload research images directly to private storage while the server keeps each
            hospital&apos;s records isolated.
          </p>
          <ul className="security-points" aria-label="Security characteristics">
            <li>Private bucket</li>
            <li>Server-authorized</li>
            <li>Short-lived links</li>
          </ul>
        </div>
        <div className="active-identity" aria-label="Current development identity">
          <span className="active-identity__dot" aria-hidden="true" />
          <span>
            <small>Active workspace</small>
            <strong>{selectedUser.name}</strong>
            <span>{selectedUser.companyName}</span>
          </span>
        </div>
      </header>

      <section className="identity-panel" aria-labelledby="identity-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Tenant isolation demo</p>
            <h2 id="identity-heading">Choose a development identity</h2>
          </div>
          <p>
            Switch hospitals to verify that each identity sees only its own company&apos;s uploads.
            Previous records are cleared before the next workspace loads.
          </p>
        </div>

        <fieldset className="identity-switch" disabled={userSwitchDisabled}>
          <legend className="visually-hidden">Switch development user</legend>
          {developmentUsers.map((user) => {
            const isSelected = selectedUser.id === user.id;
            return (
              <label className="identity-option" key={user.id}>
                <input
                  checked={isSelected}
                  className="identity-option__input"
                  name="development-user"
                  onChange={() => selectUser(user)}
                  type="radio"
                  value={user.id}
                />
                <span className="identity-option__content">
                  <span className="identity-option__avatar" aria-hidden="true">
                    {user.name === "Dana" ? "DA" : "DV"}
                  </span>
                  <span className="identity-option__label">
                    <strong>{user.name}</strong>
                    <small>{user.companyName}</small>
                  </span>
                  <span className="identity-option__status">
                    {isSelected ? "Active" : "Switch"}
                  </span>
                </span>
              </label>
            );
          })}
        </fieldset>
      </section>

      <div className="workspace-grid">
        <section className="panel upload-panel" aria-labelledby="upload-heading">
          <div className="panel__heading">
            <span className="step-number" aria-hidden="true">1</span>
            <div>
              <p className="eyebrow">New research asset</p>
              <h2 id="upload-heading">Upload an image</h2>
            </div>
          </div>

          <form className="upload-form" onSubmit={submitUpload}>
            <label className="field">
              <span>Sample ID</span>
              <input
                disabled={uploadInProgress}
                onChange={(event) => setSampleId(event.target.value)}
                placeholder="e.g. study-2026-014"
                required
                value={sampleId}
              />
            </label>

            <label className="field">
              <span>Classification</span>
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

            <label className="field field--file">
              <span>Image file</span>
              <input
                accept="image/png,image/jpeg,image/webp"
                disabled={uploadInProgress}
                key={fileInputKey}
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                required
                type="file"
              />
              <small>PNG, JPEG or WebP · maximum 10 MiB</small>
            </label>

            <button className="primary-button" disabled={uploadInProgress} type="submit">
              {uploadInProgress ? "Uploading…" : "Upload image"}
            </button>
          </form>

          <section className="feedback" aria-atomic="true" aria-live="polite">
            {uploadState.kind === "initiating" && <p>Preparing a secure upload…</p>}
            {uploadState.kind === "uploading" && <p>Uploading image directly to private storage…</p>}
            {uploadState.kind === "confirming" && <p>Confirming the stored image…</p>}
            {uploadState.kind === "success" && (
              <p className="feedback--success">
                Image uploaded and confirmed. Current status: {formatStatus(uploadState.status)}.
              </p>
            )}
            {uploadState.kind === "error" && <p className="feedback--error" role="alert">{uploadState.message}</p>}
          </section>
        </section>

        <section
          className="panel records-panel"
          aria-busy={recordLoadState.kind === "loading"}
          aria-labelledby="records-heading"
        >
          <div className="records-header">
            <div className="panel__heading">
              <span className="step-number" aria-hidden="true">2</span>
              <div>
                <p className="eyebrow">{selectedUser.companyName} workspace</p>
                <h2 id="records-heading">Accessible uploads</h2>
              </div>
            </div>
            <div className="records-header__actions">
              {recordLoadState.kind === "ready" && (
                <span className="record-count">{records.length} {records.length === 1 ? "upload" : "uploads"}</span>
              )}
              <button
                className="secondary-button"
                disabled={recordLoadState.kind === "loading"}
                onClick={() => refreshRecords()}
                type="button"
              >
                Refresh
              </button>
            </div>
          </div>

          <section className="feedback" aria-atomic="true" aria-live="polite">
            {recordLoadState.kind === "loading" && <p>Refreshing accessible upload records…</p>}
            {recordLoadState.kind === "error" && (
              <p className="feedback--error" role="alert">
                Could not refresh accessible records: {recordLoadState.message}
              </p>
            )}
            {recordLoadState.kind === "ready" && records.length === 0 && (
              <div className="empty-state">
                <span aria-hidden="true">✓</span>
                <h3>No accessible uploads</h3>
                <p>{selectedUser.name} can see only uploads owned by {selectedUser.companyName}.</p>
              </div>
            )}
            {backgroundRefreshError !== null && (
              <p className="feedback--error" role="alert">{backgroundRefreshError}</p>
            )}
          </section>

          {records.length > 0 && (
            <ul className="record-list" aria-label="Accessible upload records">
              {records.map((record) => (
                <li className="record-card" key={record.upload_id}>
                  <div className="record-card__topline">
                    <h3 title={record.filename}>{record.filename}</h3>
                    <span className={`status-pill status-pill--${record.status}`}>
                      {formatStatus(record.status)}
                    </span>
                  </div>
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
                      <dt>Created</dt>
                      <dd>
                        <time dateTime={record.created_at}>{formatCreatedAt(record.created_at)}</time>
                      </dd>
                    </div>
                  </dl>
                  <button
                    className="secondary-button record-card__download"
                    disabled={downloadInProgress || record.status === "pending_upload"}
                    onClick={() => void downloadUpload(record)}
                    type="button"
                  >
                    {downloadState.kind === "requesting" &&
                    downloadState.uploadId === record.upload_id
                      ? "Preparing…"
                      : "Download"}
                  </button>
                  {record.status === "pending_upload" && (
                    <p className="record-card__note">Download is available after confirmation.</p>
                  )}
                </li>
              ))}
            </ul>
          )}

          <section className="feedback" aria-atomic="true" aria-live="polite">
            {downloadState.kind === "success" && (
              <p className="feedback--success">Download started for {downloadState.filename}.</p>
            )}
            {downloadState.kind === "error" && (
              <p className="feedback--error" role="alert">{downloadState.message}</p>
            )}
          </section>
        </section>
      </div>
    </main>
  );
}
