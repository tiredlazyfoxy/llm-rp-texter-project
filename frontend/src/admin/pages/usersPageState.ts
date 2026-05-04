import { makeAutoObservable, runInAction } from "mobx";
import type { AdminUserResponse } from "../../types/admin";
import { disableUser, listUsers } from "../../api/admin";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

/**
 * Page state for `UsersPage` (`/admin/`).
 *
 * Holds the users-list trio. Modal open flags / targets are
 * component-local UI state and stay as plain `useState` in the page —
 * see `frontend-state.md` line 41.
 */
export class UsersPageState {
  users: AdminUserResponse[] = [];
  usersStatus: AsyncStatus = "idle";
  usersError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

export async function loadUsers(state: UsersPageState, signal: AbortSignal): Promise<void> {
  state.usersStatus = "loading";
  state.usersError = null;
  try {
    const users = await listUsers(signal);
    runInAction(() => {
      state.users = users;
      state.usersStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.usersStatus = "error";
      state.usersError = err instanceof Error ? err.message : String(err);
    });
  }
}

export function clearUsersError(state: UsersPageState): void {
  state.usersError = null;
}

/**
 * Confirm + disable a user, then refresh the list.
 * Returns true on success, false on cancel/abort/error.
 */
export async function disableUserAction(
  state: UsersPageState,
  user: AdminUserResponse,
  signal: AbortSignal,
): Promise<boolean> {
  if (!window.confirm(`Disable user "${user.username}"? They will no longer be able to log in.`)) {
    return false;
  }
  try {
    await disableUser(user.id, signal);
    await loadUsers(state, signal);
    return true;
  } catch (err) {
    if (signal.aborted) return false;
    runInAction(() => {
      state.usersError = err instanceof Error ? err.message : "Failed to disable user";
    });
    return false;
  }
}
