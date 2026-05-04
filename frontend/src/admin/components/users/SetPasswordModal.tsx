import { useState } from "react";
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

interface SetPasswordModalProps {
  opened: boolean;
  user: AdminUserResponse;
  onClose: () => void;
  onSaved: () => void;
}

export function SetPasswordModal({ opened, user, onClose, onSaved }: SetPasswordModalProps) {
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setPassword("");
    setPasswordConfirm("");
    setError(null);
    setLoading(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async () => {
    setError(null);

    if (password !== passwordConfirm) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 6) {
      setError("Password too short (min 6)");
      return;
    }

    setLoading(true);
    try {
      await setUserPassword(user.id, {
        password,
        password_confirm: passwordConfirm,
      });
      handleClose();
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to set password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={handleClose} title="Set Password" size="sm">
      <Stack>
        <Text size="sm" c="dimmed">Setting password for <strong>{user.username}</strong></Text>

        {error && (
          <Alert color="red" withCloseButton onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <PasswordInput
          label="New Password"
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
        />
        <PasswordInput
          label="Confirm Password"
          value={passwordConfirm}
          onChange={(e) => setPasswordConfirm(e.currentTarget.value)}
        />

        <Button onClick={handleSubmit} loading={loading}>
          Set Password
        </Button>
      </Stack>
    </Modal>
  );
}
