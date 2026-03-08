export interface UserResponse {
  id: string;
  username: string;
  role: "admin" | "editor" | "player";
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
}

export interface CreateDBRequest {
  admin_username: string;
  password: string;
  password_confirm: string;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
  new_password_confirm: string;
}

export interface AuthStatusResponse {
  needs_setup: boolean;
}
