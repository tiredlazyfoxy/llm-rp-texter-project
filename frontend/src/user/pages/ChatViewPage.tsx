import { useEffect, useState } from "react";
import {
  ActionIcon,
  Badge,
  Group,
  Text,
  Tooltip,
} from "@mantine/core";
import { IconSettings } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import { chatStore } from "../stores/ChatStore";
import { MessageHistory } from "../components/MessageHistory";
import { ChatInput } from "../components/ChatInput";
import { VariantSelector } from "../components/VariantSelector";
import { StatsPanel } from "../components/StatsPanel";
import { ChatSettingsPanel } from "../components/ChatSettingsPanel";
import { ChatMemoriesButton } from "../components/ChatMemoriesModal";

function _chatIdFromPath(): string {
  const match = window.location.pathname.match(/\/chat\/(\d+)/);
  return match?.[1] ?? "";
}

export const ChatViewPage = observer(function ChatViewPage() {
  const chatId = _chatIdFromPath();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const session = chatStore.currentChat?.session;

  useEffect(() => {
    chatStore.loadPublicWorlds().catch(() => {});
    chatStore.loadChatDetail(chatId);
  }, [chatId]);

  if (chatStore.isLoading) {
    return (
      <div style={{ display: "flex", height: "100%", alignItems: "center", justifyContent: "center" }}>
        <Text c="dimmed">Loading…</Text>
      </div>
    );
  }

  if (!session) {
    return (
      <div style={{ display: "flex", height: "100%", alignItems: "center", justifyContent: "center" }}>
        <Text c="dimmed">Chat not found.</Text>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "100%", flexDirection: "column" }}>
      {/* Header */}
      <Group
        px="md"
        py="xs"
        justify="space-between"
        style={{ borderBottom: "1px solid var(--mantine-color-dark-4)", flexShrink: 0 }}
      >
        <Group gap="xs">
          <Text size="sm" fw={600}>{session.world_name}</Text>
          <Text size="sm" c="dimmed">—</Text>
          <Text size="sm">{session.character_name}</Text>
          {session.status === "archived" && (
            <Badge size="sm" color="gray" variant="light">archived</Badge>
          )}
        </Group>
        <Group gap="xs">
          <ChatMemoriesButton />
          <Tooltip label="Settings">
            <ActionIcon variant="subtle" color="gray" size="md" onClick={() => setSettingsOpen(true)}>
              <IconSettings size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      {/* Main area */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
          <MessageHistory />
          <VariantSelector />
          <ChatInput />
        </div>
        <StatsPanel />
      </div>

      <ChatSettingsPanel opened={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
});
