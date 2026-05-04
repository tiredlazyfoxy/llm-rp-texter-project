import { request } from "./client";
import type {
  AdminCreateUserRequest,
  AdminSetPasswordRequest,
  AdminSetRoleRequest,
  AdminUserResponse,
} from "../types/admin";

const BASE = "/api/admin/users";

export async function listUsers(signal?: AbortSignal): Promise<AdminUserResponse[]> {
  return request<AdminUserResponse[]>(BASE, { signal });
}

export async function createUser(
  data: AdminCreateUserRequest,
  signal?: AbortSignal,
): Promise<AdminUserResponse> {
  return request<AdminUserResponse>(BASE, {
    method: "POST",
    body: data,
    signal,
  });
}

export async function setUserPassword(
  userId: string,
  data: AdminSetPasswordRequest,
  signal?: AbortSignal,
): Promise<void> {
  return request<void>(`${BASE}/${userId}/password`, {
    method: "PUT",
    body: data,
    signal,
  });
}

export async function setUserRole(
  userId: string,
  data: AdminSetRoleRequest,
  signal?: AbortSignal,
): Promise<void> {
  return request<void>(`${BASE}/${userId}/role`, {
    method: "PUT",
    body: data,
    signal,
  });
}

export async function disableUser(userId: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/${userId}/disable`, {
    method: "PUT",
    signal,
  });
}
