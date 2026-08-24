import { useEffect, useState } from "react";

import { createApiClient } from "./api";
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

type RecordLoadState =
  | { kind: "loading" }
  | { kind: "ready" }
  | { kind: "error"; message: string };

export function App() {
  const [selectedUser, setSelectedUser] = useState<DevelopmentUser>(developmentUsers[0]);
  const [records, setRecords] = useState<UploadRecord[]>([]);
  const [recordLoadState, setRecordLoadState] = useState<RecordLoadState>({ kind: "loading" });

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
          message: error instanceof Error ? error.message : "Request could not be completed",
        });
      });

    return () => {
      isCurrentRequest = false;
      controller.abort();
    };
  }, [selectedUser.id]);

  function selectUser(user: DevelopmentUser): void {
    if (user.id === selectedUser.id) {
      return;
    }

    // Clear the old tenant's data before the new tenant's request can resolve.
    setRecords([]);
    setRecordLoadState({ kind: "loading" });
    setSelectedUser(user);
  }

  return (
    <main>
      <h1>Secure Research Image Uploads</h1>
      <p>
        Development identity: <strong>{selectedUser.name}</strong> ({selectedUser.companyName})
      </p>

      <fieldset>
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

      <section aria-live="polite" aria-atomic="true">
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
