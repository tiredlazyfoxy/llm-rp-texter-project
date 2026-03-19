export interface AdminUserResponse {
  id: string;
  username: string;
  role: "admin" | "editor" | "player";
  last_login: string | null;
}

export interface AdminCreateUserRequest {
  username: string;
  password: string;
  password_confirm: string;
  role: "admin" | "editor" | "player";
}

export interface AdminSetPasswordRequest {
  password: string;
  password_confirm: string;
}

export interface AdminSetRoleRequest {
  role: "admin" | "editor" | "player";
}
