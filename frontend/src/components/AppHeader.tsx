import { useState } from "react";
import { Group, Menu, Text, UnstyledButton } from "@mantine/core";
import { getCurrentUser, logout } from "../auth";
import { ChangePasswordModal } from "./ChangePasswordModal";
import { TranslationSettingsModal } from "./TranslationSettingsModal";

export function AppHeader() {
  const user = getCurrentUser();
  const [pwdModalOpen, setPwdModalOpen] = useState(false);
  const [translateModalOpen, setTranslateModalOpen] = useState(false);

  return (
    <>
      <Group
        h={48}
        px="md"
        justify="flex-end"
        style={{ flexShrink: 0 }}
      >
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
              <Menu.Item onClick={() => setTranslateModalOpen(true)}>
                Translation settings
              </Menu.Item>
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

      <TranslationSettingsModal
        opened={translateModalOpen}
        onClose={() => setTranslateModalOpen(false)}
      />
    </>
  );
}
