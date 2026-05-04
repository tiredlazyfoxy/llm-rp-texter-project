import { useState } from "react";
import {
  Alert,
  Button,
  Modal,
  PasswordInput,
  Select,
  Stack,
  TextInput,
} from "@mantine/core";
import { createUser } from "../../../api/admin";

interface CreateUserModalProps {
  opened: boolean;
  onClose: () => void;
  onCreated: () => void;
}

const ROLE_OPTIONS = [
  { value: "player", label: "Player" },
  { value: "editor", label: "Editor" },
  { value: "admin", label: "Admin" },
];

export function CreateUserModal({ opened, onClose, onCreated }: CreateUserModalProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [role, setRole] = useState<string>("player");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setUsername("");
    setPassword("");
    setPasswordConfirm("");
    setRole("player");
    setError(null);
    setLoading(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async () => {
    setError(null);

    if (!username.trim()) {
      setError("Username is required");
      return;
    }
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
      await createUser({
        username: username.trim(),
        password,
        password_confirm: passwordConfirm,
        role: role as "admin" | "editor" | "player",
      });
      handleClose();
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create user");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={handleClose} title="Create User" size="sm">
      <Stack>
        {error && (
          <Alert color="red" withCloseButton onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <TextInput
          label="Username"
          value={username}
          onChange={(e) => setUsername(e.currentTarget.value)}
        />
        <PasswordInput
          label="Password"
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
        />
        <PasswordInput
          label="Confirm Password"
          value={passwordConfirm}
          onChange={(e) => setPasswordConfirm(e.currentTarget.value)}
        />
        <Select
          label="Role"
          data={ROLE_OPTIONS}
          value={role}
          onChange={(v) => v && setRole(v)}
        />

        <Button onClick={handleSubmit} loading={loading}>
          Create
        </Button>
      </Stack>
    </Modal>
  );
}
