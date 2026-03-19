import { useState } from "react";
import {
  Alert,
  Button,
  Modal,
  PasswordInput,
  Stack,
} from "@mantine/core";
import { changePassword } from "../api/auth";

interface ChangePasswordModalProps {
  opened: boolean;
  onClose: () => void;
}

export function ChangePasswordModal({ opened, onClose }: ChangePasswordModalProps) {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setOldPassword("");
    setNewPassword("");
    setNewPasswordConfirm("");
    setError(null);
    setLoading(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async () => {
    setError(null);

    if (newPassword !== newPasswordConfirm) {
      setError("New passwords do not match");
      return;
    }

    if (newPassword.length < 6) {
      setError("Password too short (min 6)");
      return;
    }

    setLoading(true);
    try {
      const res = await changePassword({
        old_password: oldPassword,
        new_password: newPassword,
        new_password_confirm: newPasswordConfirm,
      });
      localStorage.setItem("token", res.token);
      handleClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to change password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={handleClose} title="Change Password" size="sm">
      <Stack>
        {error && (
          <Alert color="red" onClose={() => setError(null)} withCloseButton>
            {error}
          </Alert>
        )}

        <PasswordInput
          label="Current Password"
          value={oldPassword}
          onChange={(e) => setOldPassword(e.currentTarget.value)}
        />
        <PasswordInput
          label="New Password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.currentTarget.value)}
        />
        <PasswordInput
          label="Confirm New Password"
          value={newPasswordConfirm}
          onChange={(e) => setNewPasswordConfirm(e.currentTarget.value)}
        />

        <Button onClick={handleSubmit} loading={loading}>
          Change Password
        </Button>
      </Stack>
    </Modal>
  );
}
