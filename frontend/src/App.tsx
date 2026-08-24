import { FormEvent, useEffect, useState } from "react";

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

  const uploadInProgress = ["initiating", "uploading", "confirming"].includes(uploadState.kind);

  function refreshRecords(): void {
    setRecords([]);
    setRecordLoadState({ kind: "loading" });
    setRecordRefreshVersion((version) => version + 1);
  }

  function selectUser(user: DevelopmentUser): void {
    if (user.id === selectedUser.id || uploadInProgress) {
      return;
    }

    // Clear the old tenant's data before the new tenant's request can resolve.
    setRecords([]);
    setRecordLoadState({ kind: "loading" });
    setUploadState({ kind: "idle" });
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

  return (
    <main>
      <h1>Secure Research Image Uploads</h1>
      <p>
        Development identity: <strong>{selectedUser.name}</strong> ({selectedUser.companyName})
      </p>

      <fieldset disabled={uploadInProgress}>
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

      <section aria-atomic="true" aria-live="polite">
        {recordLoadState.kind === "loading" && <p>Refreshing accessible upload records…</p>}
        {recordLoadState.kind === "ready" && (
          <p>Accessible records refreshed: {records.length}.</p>
        )}
        {recordLoadState.kind === "error" && (
          <p role="alert">Could not refresh accessible records: {recordLoadState.message}</p>
        )}
      </section>
    </main>
  );
}
