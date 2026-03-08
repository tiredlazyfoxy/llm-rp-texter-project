import { useCallback, useEffect, useState } from "react";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Menu,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { IconDots, IconLock, IconShield, IconUserOff, IconUserPlus } from "@tabler/icons-react";
import { formatDate } from "../../utils/formatDate";
import type { AdminUserResponse } from "../../types/admin";
import { disableUser, listUsers } from "../../api/admin";
import { CreateUserModal } from "../components/CreateUserModal";
import { SetPasswordModal } from "../components/SetPasswordModal";
import { SetRoleModal } from "../components/SetRoleModal";

export function UsersPage() {
  const [users, setUsers] = useState<AdminUserResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [passwordTarget, setPasswordTarget] = useState<AdminUserResponse | null>(null);
  const [roleTarget, setRoleTarget] = useState<AdminUserResponse | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(await listUsers());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleDisable = async (user: AdminUserResponse) => {
    if (!window.confirm(`Disable user "${user.username}"? They will no longer be able to log in.`)) return;
    try {
      await disableUser(user.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to disable user");
    }
  };

  const isDisabled = (user: AdminUserResponse) => user.last_login === null && user.role !== "admin";

  const fmtDate = (iso: string | null) => formatDate(iso, "Never");

  const roleBadgeColor = (role: string) => {
    if (role === "admin") return "red";
    if (role === "editor") return "blue";
    return "gray";
  };

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>Users</Title>
        <Button leftSection={<IconUserPlus size={16} />} size="sm" onClick={() => setCreateOpen(true)}>
          Create User
        </Button>
      </Group>

      {error && (
        <Alert color="red" mb="md" withCloseButton onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Group justify="center" py="xl"><Loader /></Group>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Username</Table.Th>
              <Table.Th>Role</Table.Th>
              <Table.Th>Last Login</Table.Th>
              <Table.Th w={60} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {users.map((user) => (
              <Table.Tr key={user.id} style={isDisabled(user) ? { opacity: 0.5 } : undefined}>
                <Table.Td>
                  <Text size="sm">{user.username}</Text>
                </Table.Td>
                <Table.Td>
                  <Badge color={roleBadgeColor(user.role)} variant="light" size="sm">
                    {user.role}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">{fmtDate(user.last_login)}</Text>
                </Table.Td>
                <Table.Td>
                  <Menu shadow="md" width={180} position="bottom-end">
                    <Menu.Target>
                      <ActionIcon variant="subtle" color="gray" size="sm">
                        <IconDots size={16} />
                      </ActionIcon>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Item
                        leftSection={<IconLock size={14} />}
                        onClick={() => setPasswordTarget(user)}
                      >
                        Set Password
                      </Menu.Item>
                      <Menu.Item
                        leftSection={<IconShield size={14} />}
                        onClick={() => setRoleTarget(user)}
                      >
                        Set Role
                      </Menu.Item>
                      <Menu.Divider />
                      <Menu.Item
                        color="red"
                        leftSection={<IconUserOff size={14} />}
                        onClick={() => handleDisable(user)}
                      >
                        Disable
                      </Menu.Item>
                    </Menu.Dropdown>
                  </Menu>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <CreateUserModal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={refresh}
      />

      {passwordTarget && (
        <SetPasswordModal
          opened
          user={passwordTarget}
          onClose={() => setPasswordTarget(null)}
          onSaved={refresh}
        />
      )}

      {roleTarget && (
        <SetRoleModal
          opened
          user={roleTarget}
          onClose={() => setRoleTarget(null)}
          onSaved={refresh}
        />
      )}
    </Container>
  );
}
