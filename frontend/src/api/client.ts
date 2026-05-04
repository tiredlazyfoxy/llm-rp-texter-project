import { getToken } from "../auth";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Headers for raw `fetch()` callers (streaming modules) — JSON content type + Bearer token. */
export function authHeaders(): HeadersInit {
  const token = getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  /** Plain JS value — `client.request` JSON-stringifies. Leave undefined for GET / DELETE without body. */
  body?: unknown;
  signal?: AbortSignal;
}

/**
 * Authenticated JSON request.
 * - Adds `Authorization: Bearer <token>` if a token is present.
 * - Serializes `body` via JSON.stringify when provided.
 * - Throws `ApiError(status, message, details)` on non-2xx responses.
 * - Returns `undefined as T` on 204 No Content.
 * - Forwards `signal` to fetch.
 *
 * For multipart bodies (file upload) or blob downloads, use `fetch` directly with `authHeaders()`
 * (token only, no Content-Type) and call `throwApiError(res)` on failure — see worlds.uploadDocuments.
 */
export async function request<T>(url: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  });

  if (!res.ok) await throwApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Throw `ApiError` from a non-OK response. Use when bypassing `request<T>` (raw fetch for multipart / blob). */
export async function throwApiError(res: Response): Promise<never> {
  const body = await res.json().catch(() => null);
  const message =
    (body && typeof body === "object" && "detail" in body && typeof body.detail === "string"
      ? body.detail
      : null) ?? res.statusText;
  throw new ApiError(res.status, message, body);
}
