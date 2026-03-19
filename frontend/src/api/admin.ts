import { authRequest } from "./request";
import type {
  AdminCreateUserRequest,
  AdminSetPasswordRequest,
  AdminSetRoleRequest,
  AdminUserResponse,
} from "../types/admin";

const BASE = "/api/admin/users";

export async function listUsers(): Promise<AdminUserResponse[]> {
  return authRequest<AdminUserResponse[]>(BASE);
}

export async function createUser(
  data: AdminCreateUserRequest,
): Promise<AdminUserResponse> {
  return authRequest<AdminUserResponse>(BASE, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function setUserPassword(
  userId: string,
  data: AdminSetPasswordRequest,
): Promise<void> {
  return authRequest<void>(`${BASE}/${userId}/password`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function setUserRole(
  userId: string,
  data: AdminSetRoleRequest,
): Promise<void> {
  return authRequest<void>(`${BASE}/${userId}/role`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function disableUser(userId: string): Promise<void> {
  return authRequest<void>(`${BASE}/${userId}/disable`, {
    method: "PUT",
  });
}
