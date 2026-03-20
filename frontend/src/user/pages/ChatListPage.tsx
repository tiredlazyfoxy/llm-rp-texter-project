import { useEffect, useState } from "react";
import {
  ActionIcon,
  Badge,
  Button,
  Container,
  Group,
  Modal,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { IconTrash } from "@tabler/icons-react";
import { listMyChats, deleteChat } from "../../api/chat";
import { formatDate } from "../../utils/formatDate";

export function ChatListPage() {
  const [chats, setChats] = useState<ChatSessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<ChatSessionItem | null>(null);

  useEffect(() => {
    listMyChats()
      .then(setChats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete() {
    if (!deleteTarget) return;
    await deleteChat(deleteTarget.id).catch(() => {});
    setChats((prev) => prev.filter((c) => c.id !== deleteTarget.id));
    setDeleteTarget(null);
  }

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>My Chats</Title>
      </Group>

      {loading ? (
        <Text c="dimmed">Loading…</Text>
      ) : chats.length === 0 ? (
        <Text c="dimmed">No chats yet. Click a world in the sidebar to start one.</Text>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>World</Table.Th>
              <Table.Th>Character</Table.Th>
              <Table.Th>Turns</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Last activity</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {chats.map((chat) => (
              <Table.Tr
                key={chat.id}
                style={{ cursor: "pointer" }}
                onClick={() => { window.location.href = `/chat/${chat.id}`; }}
              >
                <Table.Td>{chat.world_name}</Table.Td>
                <Table.Td>{chat.character_name}</Table.Td>
                <Table.Td>{chat.current_turn}</Table.Td>
                <Table.Td>
                  <Badge
                    size="sm"
                    color={chat.status === "active" ? "green" : "gray"}
                    variant="light"
                  >
                    {chat.status}
                  </Badge>
                </Table.Td>
                <Table.Td>{formatDate(chat.modified_at)}</Table.Td>
                <Table.Td>
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); setDeleteTarget(chat); }}
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
        opened={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete chat?"
        size="sm"
      >
        <Text size="sm" mb="md">
          Delete "{deleteTarget?.character_name}" in {deleteTarget?.world_name}? This cannot be undone.
        </Text>
        <Group justify="flex-end">
          <Button variant="subtle" onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button color="red" onClick={handleDelete}>Delete</Button>
        </Group>
      </Modal>
    </Container>
  );
}
