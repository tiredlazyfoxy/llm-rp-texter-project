import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate } from "react-router-dom";
import {
  ActionIcon,
  Button,
  Container,
  Group,
  Modal,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { IconTrash } from "@tabler/icons-react";
import { formatDate } from "../../utils/formatDate";
import {
  ChatListPageState,
  loadChats,
  deleteSelectedChat,
} from "./chatListPageState";

export const ChatListPage = observer(function ChatListPage() {
  const [state] = useState(() => new ChatListPageState());
  const navigate = useNavigate();

  useEffect(() => {
    const ctrl = new AbortController();
    loadChats(state, ctrl.signal);
    return () => ctrl.abort();
  }, []);

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>My Chats</Title>
      </Group>

      {state.chatsStatus === "loading" || state.chatsStatus === "idle" ? (
        <Text c="dimmed">Loading…</Text>
      ) : state.chatsStatus === "error" ? (
        <Text c="red">{state.chatsError}</Text>
      ) : state.chats.length === 0 ? (
        <Text c="dimmed">No chats yet. Click a world in the sidebar to start one.</Text>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>World</Table.Th>
              <Table.Th>Character</Table.Th>
              <Table.Th>Location</Table.Th>
              <Table.Th>Last activity</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {state.chats.map((chat) => (
              <Table.Tr
                key={chat.id}
                style={{ cursor: "pointer" }}
                onClick={() => navigate(`/chat/${chat.id}`)}
              >
                <Table.Td>{chat.world_name}</Table.Td>
                <Table.Td>{chat.character_name}</Table.Td>
                <Table.Td>{chat.current_location_name || "—"}</Table.Td>
                <Table.Td>{formatDate(chat.modified_at)}</Table.Td>
                <Table.Td>
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      state.deleteTarget = chat;
                    }}
                  >
                    <IconTrash size={14} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal
        opened={state.deleteTarget !== null}
        onClose={() => { state.deleteTarget = null; }}
        title="Delete chat?"
        size="sm"
      >
        <Text size="sm" mb="md">
          Delete "{state.deleteTarget?.character_name}" in {state.deleteTarget?.world_name}? This cannot be undone.
        </Text>
        {state.deleteStatus === "error" && (
          <Text c="red" size="sm" mb="md">{state.deleteError}</Text>
        )}
        <Group justify="flex-end">
          <Button variant="subtle" onClick={() => { state.deleteTarget = null; }}>Cancel</Button>
          <Button
            color="red"
            loading={state.deleteStatus === "loading"}
            onClick={() => {
              const ctrl = new AbortController();
              deleteSelectedChat(state, ctrl.signal);
            }}
          >
            Delete
          </Button>
        </Group>
      </Modal>
    </Container>
  );
});
