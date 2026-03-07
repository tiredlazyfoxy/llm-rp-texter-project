import { useEffect, useState } from "react";
import {
  MantineProvider,
  Container,
  Title,
  Tabs,
  TextInput,
  PasswordInput,
  Button,
  Alert,
  FileInput,
  Stack,
} from "@mantine/core";
import "@mantine/core/styles.css";
import { getAuthStatus, login, setupCreate, setupImport } from "../api/auth";

export function Login() {
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Login form
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  // Setup form
  const [adminUsername, setAdminUsername] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminPasswordConfirm, setAdminPasswordConfirm] = useState("");
  const [importFile, setImportFile] = useState<File | null>(null);

  useEffect(() => {
    getAuthStatus()
      .then((r) => setNeedsSetup(r.needs_setup))
      .catch((e) => setError(e.message));
  }, []);

  const handleLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await login({ username, password });
      localStorage.setItem("token", res.token);
      window.location.href = "/";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    setError(null);
    if (adminPassword !== adminPasswordConfirm) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      const res = await setupCreate({
        admin_username: adminUsername,
        password: adminPassword,
        password_confirm: adminPasswordConfirm,
      });
      localStorage.setItem("token", res.token);
      window.location.href = "/";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Setup failed");
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    if (!importFile) return;
    setError(null);
    setLoading(true);
    try {
      await setupImport(importFile);
      setNeedsSetup(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setLoading(false);
    }
  };

  if (needsSetup === null) {
    return (
      <MantineProvider>
        <Container size="xs" mt="xl">
          <Title order={2}>Loading...</Title>
        </Container>
      </MantineProvider>
    );
  }

  return (
    <MantineProvider>
      <Container size="xs" mt="xl">
        <Title order={1} mb="lg">
          LLMRP
        </Title>

        {error && (
          <Alert color="red" mb="md" onClose={() => setError(null)} withCloseButton>
            {error}
          </Alert>
        )}

        {needsSetup ? (
          <Tabs defaultValue="create">
            <Tabs.List>
              <Tabs.Tab value="create">Create Database</Tabs.Tab>
              <Tabs.Tab value="import">Import Database</Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="create" pt="md">
              <Stack>
                <TextInput
                  label="Admin Username"
                  value={adminUsername}
                  onChange={(e) => setAdminUsername(e.currentTarget.value)}
                />
                <PasswordInput
                  label="Password"
                  value={adminPassword}
                  onChange={(e) => setAdminPassword(e.currentTarget.value)}
                />
                <PasswordInput
                  label="Confirm Password"
                  value={adminPasswordConfirm}
                  onChange={(e) => setAdminPasswordConfirm(e.currentTarget.value)}
                />
                <Button onClick={handleCreate} loading={loading}>
                  Create Database
                </Button>
              </Stack>
            </Tabs.Panel>

            <Tabs.Panel value="import" pt="md">
              <Stack>
                <FileInput
                  label="Database ZIP file"
                  accept=".zip"
                  value={importFile}
                  onChange={setImportFile}
                />
                <Button onClick={handleImport} loading={loading} disabled={!importFile}>
                  Import Database
                </Button>
              </Stack>
            </Tabs.Panel>
          </Tabs>
        ) : (
          <Stack>
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
            <Button onClick={handleLogin} loading={loading}>
              Log In
            </Button>
          </Stack>
        )}
      </Container>
    </MantineProvider>
  );
}
