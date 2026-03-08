import type { UserResponse } from "./types/user";

interface JwtPayload {
  user_id: string;
  username: string;
  role: "admin" | "editor" | "player";
  exp: number;
}

export function getToken(): string | null {
  return localStorage.getItem("token");
}

function parsePayload(token: string): JwtPayload | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1])) as JwtPayload;
    return payload;
  } catch {
    return null;
  }
}

export function getCurrentUser(): Pick<UserResponse, "username" | "role"> | null {
  const token = getToken();
  if (!token) return null;
  const payload = parsePayload(token);
  if (!payload) return null;
  return { username: payload.username, role: payload.role };
}

export function logout(): void {
  localStorage.removeItem("token");
  window.location.href = "/login/";
}
