import { useEffect, useState } from "react";
import { makeAutoObservable, runInAction } from "mobx";
import { observer } from "mobx-react-lite";
import {
  Alert,
  Button,
  Modal,
  PasswordInput,
  Stack,
  Text,
} from "@mantine/core";
import type { AdminUserResponse } from "../../../types/admin";
import { setUserPassword } from "../../../api/admin";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

interface SetPasswordDraftErrors {
  newPassword?: string;
  confirmPassword?: string;
}

/**
 * Component-local draft for the set-password modal.
 * Held in `SetPasswordModal` via `useState(() => new SetPasswordDraft())`.
 */
class SetPasswordDraft {
  newPassword = "";
  confirmPassword = "";

  serverErrors: SetPasswordDraftErrors = {};
  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  reset(): void {
    this.newPassword = "";
    this.confirmPassword = "";
    this.serverErrors = {};
    this.saveStatus = "idle";
    this.saveError = null;
  }

  get errors(): SetPasswordDraftErrors {
    const e: SetPasswordDraftErrors = {};
    if (this.newPassword.length < 6) e.newPassword = "Password too short (min 6)";
    if (this.newPassword !== this.confirmPassword) e.confirmPassword = "Passwords do not match";
    return { ...e, ...this.serverErrors };
  }

  get canSubmit(): boolean {
    return Object.keys(this.errors).length === 0 && this.saveStatus !== "loading";
  }
}

export function clearSetPasswordSaveError(draft: SetPasswordDraft): void {
  draft.saveError = null;
}

export async function submitSetPassword(
  draft: SetPasswordDraft,
  userId: string,
  signal: AbortSignal,
): Promise<boolean> {
  if (!draft.canSubmit) return false;
  draft.saveStatus = "loading";
  draft.saveError = null;
  try {
    await setUserPassword(
      userId,
      {
        password: draft.newPassword,
        password_confirm: draft.confirmPassword,
      },
      signal,
    );
    runInAction(() => {
      draft.saveStatus = "ready";
    });
    return true;
  } catch (err) {
    if (signal.aborted) return false;
    runInAction(() => {
      draft.saveStatus = "error";
      draft.saveError = err instanceof Error ? err.message : "Failed to set password";
    });
    return false;
  }
}

interface SetPasswordModalProps {
  opened: boolean;
  user: AdminUserResponse;
  onClose: () => void;
  onSaved: () => void;
}

export const SetPasswordModal = observer(function SetPasswordModal({
  opened,
  user,
  onClose,
  onSaved,
}: SetPasswordModalProps) {
  const [draft] = useState(() => new SetPasswordDraft());

  // Reset whenever the modal opens (or the target user changes).
  useEffect(() => {
    if (opened) draft.reset();
  }, [opened, user.id, draft]);

  const handleSubmit = async () => {
    if (!draft.canSubmit) return;
    const ctrl = new AbortController();
    const ok = await submitSetPassword(draft, user.id, ctrl.signal);
    if (ok) {
      onSaved();
      onClose();
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Set Password" size="sm">
      <Stack>
        <Text size="sm" c="dimmed">Setting password for <strong>{user.username}</strong></Text>

        {draft.saveError && (
          <Alert color="red" withCloseButton onClose={() => clearSetPasswordSaveError(draft)}>
            {draft.saveError}
          </Alert>
        )}

        <PasswordInput
          label="New Password"
          value={draft.newPassword}
          onChange={(e) => { draft.newPassword = e.currentTarget.value; }}
          error={draft.errors.newPassword}
        />
        <PasswordInput
          label="Confirm Password"
          value={draft.confirmPassword}
          onChange={(e) => { draft.confirmPassword = e.currentTarget.value; }}
          error={draft.errors.confirmPassword}
        />

        <Button
          onClick={handleSubmit}
          disabled={!draft.canSubmit}
          loading={draft.saveStatus === "loading"}
        >
          Set Password
        </Button>
      </Stack>
    </Modal>
  );
});
