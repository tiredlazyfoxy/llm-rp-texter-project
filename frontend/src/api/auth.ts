import type {
  AuthStatusResponse,
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
