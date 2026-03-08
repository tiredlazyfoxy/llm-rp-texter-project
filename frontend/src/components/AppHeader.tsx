import { useState } from "react";
import {
  Anchor,
  Group,
  Image,
  Menu,
  Text,
  UnstyledButton,
} from "@mantine/core";
import { getCurrentUser, logout } from "../auth";
import { ChangePasswordModal } from "./ChangePasswordModal";

export function AppHeader() {
  const user = getCurrentUser();
  const [pwdModalOpen, setPwdModalOpen] = useState(false);

  return (
    <>
      <Group
        h={48}
        px="md"
        justify="space-between"
        style={{
          borderBottom: "1px solid var(--mantine-color-dark-4)",
          flexShrink: 0,
        }}
      >
        <Anchor href="/" underline="never">
          <Group gap="xs">
            <Image src="/logo.svg" w={28} h={28} />
            <Text fw={600} size="lg" c="dimmed">
              LLMRP
            </Text>
          </Group>
        </Anchor>

        {user && (
          <Menu shadow="md" width={180} position="bottom-end">
            <Menu.Target>
              <UnstyledButton>
                <Group gap={6}>
                  <Text size="sm" c="dimmed">
                    {user.username}
                  </Text>
                  <Text size="xs" c="dimmed">
                    [{user.role}]
                  </Text>
                </Group>
              </UnstyledButton>
            </Menu.Target>

            <Menu.Dropdown>
              {user.role === "admin" && (
                <Menu.Item component="a" href="/admin/">
                  Admin
                </Menu.Item>
              )}
              <Menu.Item onClick={() => setPwdModalOpen(true)}>
                Change password
              </Menu.Item>
              <Menu.Divider />
              <Menu.Item onClick={logout}>Log out</Menu.Item>
            </Menu.Dropdown>
          </Menu>
        )}
      </Group>

      <ChangePasswordModal
        opened={pwdModalOpen}
        onClose={() => setPwdModalOpen(false)}
      />
    </>
  );
}
