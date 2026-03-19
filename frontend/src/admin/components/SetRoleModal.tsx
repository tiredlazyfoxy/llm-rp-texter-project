import { useState } from "react";
import {
  Alert,
  Button,
  Modal,
  Select,
  Stack,
  Text,
} from "@mantine/core";
import type { AdminUserResponse } from "../../types/admin";
import { setUserRole } from "../../api/admin";

interface SetRoleModalProps {
  opened: boolean;
  user: AdminUserResponse;
  onClose: () => void;
  onSaved: () => void;
}

const ROLE_OPTIONS = [
  { value: "player", label: "Player" },
  { value: "editor", label: "Editor" },
  { value: "admin", label: "Admin" },
];

export function SetRoleModal({ opened, user, onClose, onSaved }: SetRoleModalProps) {
  const [role, setRole] = useState<string>(user.role);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setRole(user.role);
    setError(null);
    setLoading(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async () => {
    setError(null);

    if (role === user.role) {
      handleClose();
      return;
    }

    setLoading(true);
    try {
      await setUserRole(user.id, {
        role: role as "admin" | "editor" | "player",
      });
      handleClose();
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to set role");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={handleClose} title="Set Role" size="sm">
      <Stack>
        <Text size="sm" c="dimmed">Changing role for <strong>{user.username}</strong></Text>

        {error && (
          <Alert color="red" withCloseButton onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Select
          label="Role"
          data={ROLE_OPTIONS}
          value={role}
          onChange={(v) => v && setRole(v)}
        />

        <Button onClick={handleSubmit} loading={loading}>
          Save
        </Button>
      </Stack>
    </Modal>
  );
}
