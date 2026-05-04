import { useEffect, useState } from "react";
import { makeAutoObservable, runInAction } from "mobx";
import { observer } from "mobx-react-lite";
import {
  Alert,
  Button,
  Modal,
  Select,
  Stack,
  Text,
} from "@mantine/core";
import type { AdminUserResponse } from "../../../types/admin";
import { setUserRole } from "../../../api/admin";

type AsyncStatus = "idle" | "loading" | "ready" | "error";
type Role = "admin" | "editor" | "player";

const ROLE_OPTIONS = [
  { value: "player", label: "Player" },
  { value: "editor", label: "Editor" },
  { value: "admin", label: "Admin" },
];

/**
 * Component-local draft for the set-role modal.
 * Held in `SetRoleModal` via `useState(() => new SetRoleDraft(user.role))`.
 */
class SetRoleDraft {
  role: Role;
  initialRole: Role;

  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;

  constructor(initialRole: Role) {
    this.role = initialRole;
    this.initialRole = initialRole;
    makeAutoObservable(this);
  }

  reset(initialRole: Role): void {
    this.role = initialRole;
    this.initialRole = initialRole;
    this.saveStatus = "idle";
    this.saveError = null;
  }

  get isDirty(): boolean {
    return this.role !== this.initialRole;
  }

  get canSubmit(): boolean {
    return this.saveStatus !== "loading";
  }
}

export function clearSetRoleSaveError(draft: SetRoleDraft): void {
  draft.saveError = null;
}

export async function submitSetRole(
  draft: SetRoleDraft,
  userId: string,
  signal: AbortSignal,
): Promise<boolean> {
  if (!draft.isDirty) return true; // no-op success — let caller close the modal
  draft.saveStatus = "loading";
  draft.saveError = null;
  try {
    await setUserRole(userId, { role: draft.role }, signal);
    runInAction(() => {
      draft.saveStatus = "ready";
    });
    return true;
  } catch (err) {
    if (signal.aborted) return false;
    runInAction(() => {
      draft.saveStatus = "error";
      draft.saveError = err instanceof Error ? err.message : "Failed to set role";
    });
    return false;
  }
}

interface SetRoleModalProps {
  opened: boolean;
  user: AdminUserResponse;
  onClose: () => void;
  onSaved: () => void;
}

export const SetRoleModal = observer(function SetRoleModal({
  opened,
  user,
  onClose,
  onSaved,
}: SetRoleModalProps) {
  const [draft] = useState(() => new SetRoleDraft(user.role));

  // Reset whenever the modal opens (or the target user changes).
  useEffect(() => {
    if (opened) draft.reset(user.role);
  }, [opened, user.id, user.role, draft]);

  const handleSubmit = async () => {
    if (!draft.canSubmit) return;
    const ctrl = new AbortController();
    const ok = await submitSetRole(draft, user.id, ctrl.signal);
    if (ok) {
      // Only refresh the list when an actual change was committed.
      if (draft.isDirty) onSaved();
      onClose();
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Set Role" size="sm">
      <Stack>
        <Text size="sm" c="dimmed">Changing role for <strong>{user.username}</strong></Text>

        {draft.saveError && (
          <Alert color="red" withCloseButton onClose={() => clearSetRoleSaveError(draft)}>
            {draft.saveError}
          </Alert>
        )}

        <Select
          label="Role"
          data={ROLE_OPTIONS}
          value={draft.role}
          onChange={(v) => { if (v) draft.role = v as Role; }}
        />

        <Button
          onClick={handleSubmit}
          disabled={!draft.canSubmit}
          loading={draft.saveStatus === "loading"}
        >
          Save
        </Button>
      </Stack>
    </Modal>
  );
});
