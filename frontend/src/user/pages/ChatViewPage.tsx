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
import { ChatPageState, loadChat } from "./chatPageState";
import { MessageHistory } from "../components/chats/MessageHistory";
import { ChatInput } from "../components/chats/ChatInput";
import { StatsPanel } from "../components/chats/StatsPanel";
import { ChatSettingsPanel } from "../components/chats/ChatSettingsPanel";
import { ChatMemoriesButton } from "../components/chats/ChatMemoriesModal";

interface ChatViewPageProps {
  chatId: string;
}

export const ChatViewPage = observer(function ChatViewPage({ chatId }: ChatViewPageProps) {
  const [state] = useState(() => new ChatPageState(chatId));
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    loadChat(state, ctrl.signal);
    return () => {
      ctrl.abort();
      state.dispose();
    };
  }, []);

  if (state.loadStatus === "loading" || state.loadStatus === "idle") {
    return (
      <div style={{ display: "flex", height: "100%", alignItems: "center", justifyContent: "center" }}>
        <Text c="dimmed">Loading…</Text>
      </div>
    );
  }

  const session = state.currentChat?.session;
  if (!session) {
    return (
      <div style={{ display: "flex", height: "100%", alignItems: "center", justifyContent: "center" }}>
        <Text c="dimmed">{state.loadError ?? "Chat not found."}</Text>
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
          <ChatMemoriesButton state={state} />
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
          <MessageHistory state={state} />
          <ChatInput state={state} />
        </div>
        <StatsPanel state={state} />
      </div>

      <ChatSettingsPanel state={state} opened={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
});
