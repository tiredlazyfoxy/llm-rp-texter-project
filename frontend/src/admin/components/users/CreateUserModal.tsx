import { useEffect, useState } from "react";
import { makeAutoObservable, runInAction } from "mobx";
import { observer } from "mobx-react-lite";
import {
  Alert,
  Button,
  Modal,
  PasswordInput,
  Select,
  Stack,
  TextInput,
} from "@mantine/core";
import type { AdminUserResponse } from "../../../types/admin";
import { createUser } from "../../../api/admin";

type AsyncStatus = "idle" | "loading" | "ready" | "error";
type Role = "admin" | "editor" | "player";

const ROLE_OPTIONS = [
  { value: "player", label: "Player" },
  { value: "editor", label: "Editor" },
  { value: "admin", label: "Admin" },
];

interface CreateUserDraftErrors {
  username?: string;
  password?: string;
  confirmPassword?: string;
}

/**
 * Component-local draft for the create-user modal.
 * Held in `CreateUserModal` via `useState(() => new CreateUserDraft())`.
 */
class CreateUserDraft {
  username = "";
  password = "";
  confirmPassword = "";
  role: Role = "player";

  serverErrors: CreateUserDraftErrors = {};
  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  reset(): void {
    this.username = "";
    this.password = "";
    this.confirmPassword = "";
    this.role = "player";
    this.serverErrors = {};
    this.saveStatus = "idle";
    this.saveError = null;
  }

  get errors(): CreateUserDraftErrors {
    const e: CreateUserDraftErrors = {};
    if (!this.username.trim()) e.username = "Username is required";
    if (this.password.length < 6) e.password = "Password too short (min 6)";
    if (this.password !== this.confirmPassword) e.confirmPassword = "Passwords do not match";
    return { ...e, ...this.serverErrors };
  }

  get isValid(): boolean {
    return Object.keys(this.errors).length === 0;
  }

  get canSubmit(): boolean {
    return this.isValid && this.saveStatus !== "loading";
  }
}

export function clearCreateUserSaveError(draft: CreateUserDraft): void {
  draft.saveError = null;
}

export async function submitCreateUser(
  draft: CreateUserDraft,
  signal: AbortSignal,
): Promise<AdminUserResponse | null> {
  if (!draft.canSubmit) return null;
  draft.saveStatus = "loading";
  draft.saveError = null;
  try {
    const created = await createUser(
      {
        username: draft.username.trim(),
        password: draft.password,
        password_confirm: draft.confirmPassword,
        role: draft.role,
      },
      signal,
    );
    runInAction(() => {
      draft.saveStatus = "ready";
    });
    return created;
  } catch (err) {
    if (signal.aborted) return null;
    runInAction(() => {
      draft.saveStatus = "error";
      draft.saveError = err instanceof Error ? err.message : "Failed to create user";
    });
    return null;
  }
}

interface CreateUserModalProps {
  opened: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export const CreateUserModal = observer(function CreateUserModal({
  opened,
  onClose,
  onCreated,
}: CreateUserModalProps) {
  const [draft] = useState(() => new CreateUserDraft());

  // Reset whenever the modal opens.
  useEffect(() => {
    if (opened) draft.reset();
  }, [opened, draft]);

  const handleSubmit = async () => {
    if (!draft.canSubmit) return;
    const ctrl = new AbortController();
    const created = await submitCreateUser(draft, ctrl.signal);
    if (created) {
      onCreated();
      onClose();
    }
  };

  const handleClose = () => {
    onClose();
  };

  return (
    <Modal opened={opened} onClose={handleClose} title="Create User" size="sm">
      <Stack>
        {draft.saveError && (
          <Alert color="red" withCloseButton onClose={() => clearCreateUserSaveError(draft)}>
            {draft.saveError}
          </Alert>
        )}

        <TextInput
          label="Username"
          value={draft.username}
          onChange={(e) => { draft.username = e.currentTarget.value; }}
          error={draft.errors.username}
        />
        <PasswordInput
          label="Password"
          value={draft.password}
          onChange={(e) => { draft.password = e.currentTarget.value; }}
          error={draft.errors.password}
        />
        <PasswordInput
          label="Confirm Password"
          value={draft.confirmPassword}
          onChange={(e) => { draft.confirmPassword = e.currentTarget.value; }}
          error={draft.errors.confirmPassword}
        />
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
          Create
        </Button>
      </Stack>
    </Modal>
  );
});
