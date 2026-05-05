import { request } from "./client";
import type {
  AdminCreateUserRequest,
  AdminSetPasswordRequest,
  AdminSetRoleRequest,
  AdminUserResponse,
} from "../types/admin";

const BASE = "/api/admin/users";

interface NewSnowflakeIdResponse {
  id: string;
}

/**
 * Pre-allocate a fresh snowflake id for a draft document. Used by
 * "create draft, persist on save" flows so the editor URL contains a
 * real id from the start. Mirrors `GET /api/admin/snowflake/new`.
 */
export async function getNewSnowflakeId(signal?: AbortSignal): Promise<string> {
  const res = await request<NewSnowflakeIdResponse>("/api/admin/snowflake/new", { signal });
  return res.id;
}

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
