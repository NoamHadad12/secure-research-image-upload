import type {
  UploadConfirmation,
  UploadInitiation,
  UploadInitiationMetadata,
  UploadRecord,
} from "./types";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

type ApiErrorBody = {
  error?: {
    message?: string;
  };
};

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export type ApiClient = {
  listUploads(signal?: AbortSignal): Promise<UploadRecord[]>;
  initiateUpload(
    metadata: UploadInitiationMetadata,
    signal?: AbortSignal,
  ): Promise<UploadInitiation>;
  confirmUpload(uploadId: string, signal?: AbortSignal): Promise<UploadConfirmation>;
};

function readErrorMessage(body: unknown): string {
  if (
    typeof body === "object" &&
    body !== null &&
    "error" in body &&
    typeof (body as ApiErrorBody).error?.message === "string"
  ) {
    return (body as ApiErrorBody).error!.message!;
  }
  return "Request could not be completed";
}

/**
 * Create a development API client for one seeded user.
 *
 * The client sends only the development user ID. The backend resolves that ID
 * to a company and remains the sole authorization authority.
 */
export function createApiClient(developmentUserId: string): ApiClient {
  async function request<T>(
    path: string,
    options: {
      body?: unknown;
      method?: "GET" | "POST";
      signal?: AbortSignal;
    } = {},
  ): Promise<T> {
    const headers: Record<string, string> = { "X-User-ID": developmentUserId };
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(`${apiBaseUrl}${path}`, {
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      headers,
      method: options.method ?? "GET",
      signal: options.signal,
    });

    if (!response.ok) {
      let body: unknown;
      try {
        body = await response.json();
      } catch {
        body = undefined;
      }
      throw new ApiError(readErrorMessage(body), response.status);
    }

    return (await response.json()) as T;
  }

  return {
    listUploads: (signal) => request<UploadRecord[]>("/api/uploads", { signal }),
    initiateUpload: (metadata, signal) =>
      request<UploadInitiation>("/api/uploads/initiate", {
        body: metadata,
        method: "POST",
        signal,
      }),
    confirmUpload: (uploadId, signal) =>
      request<UploadConfirmation>(`/api/uploads/${uploadId}/confirm`, {
        method: "POST",
        signal,
      }),
  };
}
