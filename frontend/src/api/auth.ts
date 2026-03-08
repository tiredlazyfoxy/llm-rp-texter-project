import { getToken } from "../auth";
import type {
  AuthStatusResponse,
  ChangePasswordRequest,
  CreateDBRequest,
  LoginRequest,
  LoginResponse,
} from "../types/user";

const BASE = "/api/auth";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || res.statusText);
  }
  return res.json() as Promise<T>;
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function getAuthStatus(): Promise<AuthStatusResponse> {
  return request<AuthStatusResponse>("/status");
}

export async function login(data: LoginRequest): Promise<LoginResponse> {
  return request<LoginResponse>("/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function setupCreate(
  data: CreateDBRequest
): Promise<LoginResponse> {
  return request<LoginResponse>("/setup/create", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function setupImport(file: File): Promise<AuthStatusResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${BASE}/setup/import`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || res.statusText);
  }
  return res.json() as Promise<AuthStatusResponse>;
}

export async function changePassword(
  data: ChangePasswordRequest
): Promise<LoginResponse> {
  return request<LoginResponse>("/change-password", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
}
