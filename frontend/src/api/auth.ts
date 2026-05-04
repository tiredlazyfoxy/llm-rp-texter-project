import { request as authedRequest, throwApiError } from "./client";
import type {
  AuthStatusResponse,
  ChangePasswordRequest,
  CreateDBRequest,
  LoginRequest,
  LoginResponse,
} from "../types/user";

const BASE = "/api/auth";

async function noAuthRequest<T>(
  path: string,
  opts: RequestInit & { signal?: AbortSignal } = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) await throwApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function getAuthStatus(signal?: AbortSignal): Promise<AuthStatusResponse> {
  return noAuthRequest<AuthStatusResponse>("/status", { signal });
}

export async function login(data: LoginRequest, signal?: AbortSignal): Promise<LoginResponse> {
  return noAuthRequest<LoginResponse>("/login", {
    method: "POST",
    body: JSON.stringify(data),
    signal,
  });
}

export async function setupCreate(
  data: CreateDBRequest,
  signal?: AbortSignal,
): Promise<LoginResponse> {
  return noAuthRequest<LoginResponse>("/setup/create", {
    method: "POST",
    body: JSON.stringify(data),
    signal,
  });
}

export async function setupImport(file: File, signal?: AbortSignal): Promise<AuthStatusResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${BASE}/setup/import`, {
    method: "POST",
    body: formData,
    signal,
  });
  if (!res.ok) await throwApiError(res);
  return (await res.json()) as AuthStatusResponse;
}

export async function changePassword(
  data: ChangePasswordRequest,
  signal?: AbortSignal,
): Promise<LoginResponse> {
  return authedRequest<LoginResponse>(`${BASE}/change-password`, {
    method: "POST",
    body: data,
    signal,
  });
}
