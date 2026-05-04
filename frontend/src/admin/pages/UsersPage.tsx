import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
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
import { CreateUserModal } from "../components/users/CreateUserModal";
import { SetPasswordModal } from "../components/users/SetPasswordModal";
import { SetRoleModal } from "../components/users/SetRoleModal";
import {
  UsersPageState,
  clearUsersError,
  disableUserAction,
  loadUsers,
} from "./usersPageState";

function isDisabled(user: AdminUserResponse): boolean {
  return user.last_login === null && user.role !== "admin";
}

function fmtDate(iso: string | null): string {
  return formatDate(iso, "Never");
}

function roleBadgeColor(role: string): string {
  if (role === "admin") return "red";
  if (role === "editor") return "blue";
  return "gray";
}

export const UsersPage = observer(function UsersPage() {
  const [state] = useState(() => new UsersPageState());

  // Component-local UI flags / modal targets — not page data, per
  // `frontend-state.md` line 41.
  const [createOpen, setCreateOpen] = useState(false);
  const [passwordTarget, setPasswordTarget] = useState<AdminUserResponse | null>(null);
  const [roleTarget, setRoleTarget] = useState<AdminUserResponse | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    void loadUsers(state, ctrl.signal);
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refresh = () => {
    const ctrl = new AbortController();
    void loadUsers(state, ctrl.signal);
  };

  const handleDisable = async (user: AdminUserResponse) => {
    const ctrl = new AbortController();
    await disableUserAction(state, user, ctrl.signal);
  };

  const loading = state.usersStatus === "loading" || state.usersStatus === "idle";

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>Users</Title>
        <Button leftSection={<IconUserPlus size={16} />} size="sm" onClick={() => setCreateOpen(true)}>
          Create User
        </Button>
      </Group>

      {state.usersError && (
        <Alert color="red" mb="md" withCloseButton onClose={() => clearUsersError(state)}>
          {state.usersError}
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
            {state.users.map((user) => (
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
});
