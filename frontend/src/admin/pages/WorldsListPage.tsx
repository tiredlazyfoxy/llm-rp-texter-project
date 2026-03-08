import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Menu,
  Modal,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import {
  IconCopy,
  IconDots,
  IconEdit,
  IconFileText,
  IconPlus,
  IconTrash,
} from "@tabler/icons-react";
import { getCurrentUser } from "../../auth";
import type { WorldItem } from "../../types/world";
import { cloneWorld, createWorld, deleteWorld, listWorlds } from "../../api/worlds";

// ---------------------------------------------------------------------------
// Create world modal
// ---------------------------------------------------------------------------

interface CreateWorldModalProps {
  opened: boolean;
  onClose: () => void;
  onSaved: () => void;
}

function CreateWorldModal({ opened, onClose, onSaved }: CreateWorldModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [worldStatus, setWorldStatus] = useState("draft");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (opened) {
      setName("");
      setDescription("");
      setWorldStatus("draft");
      setError(null);
    }
  }, [opened]);

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await createWorld({ name: name.trim(), description, status: worldStatus });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create world");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Create World">
      <Stack>
        {error && <Alert color="red">{error}</Alert>}
        <TextInput label="Name" value={name} onChange={e => setName(e.currentTarget.value)} required />
        <Textarea label="Description" value={description} onChange={e => setDescription(e.currentTarget.value)} minRows={3} />
        <Select
          label="Status"
          data={[
            { value: "draft", label: "Draft" },
            { value: "public", label: "Public" },
            { value: "private", label: "Private" },
            { value: "archived", label: "Archived" },
          ]}
          value={worldStatus}
          onChange={v => setWorldStatus(v || "draft")}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} loading={loading}>Create</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Status badge helper
// ---------------------------------------------------------------------------

function statusColor(s: string): string {
  if (s === "public") return "green";
  if (s === "private") return "yellow";
  if (s === "archived") return "gray";
  return "blue";
}

function formatDate(d: string | null): string {
  if (!d) return "-";
  return new Date(d).toLocaleDateString();
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function WorldsListPage() {
  const [worlds, setWorlds] = useState<WorldItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const currentUser = getCurrentUser();
  const isAdmin = currentUser?.role === "admin";

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setWorlds(await listWorlds());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load worlds");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleClone = async (world: WorldItem) => {
    try {
      await cloneWorld(world.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to clone world");
    }
  };

  const handleDelete = async (world: WorldItem) => {
    if (!window.confirm(`Delete world "${world.name}"? This will remove all documents, stats, rules, and vector data.`)) return;
    try {
      await deleteWorld(world.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete world");
    }
  };

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>Worlds</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setCreateOpen(true)}>
          Create World
        </Button>
      </Group>

      {error && <Alert color="red" mb="md" withCloseButton onClose={() => setError(null)}>{error}</Alert>}

      {loading ? (
        <Group justify="center" py="xl"><Loader /></Group>
      ) : worlds.length === 0 ? (
        <Text c="dimmed" ta="center" py="xl">No worlds yet. Create one to get started.</Text>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Modified</Table.Th>
              <Table.Th w={60} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {worlds.map(world => (
              <Table.Tr key={world.id}>
                <Table.Td>
                  <Text fw={500}>{world.name}</Text>
                  {world.description && (
                    <Text size="xs" c="dimmed" lineClamp={1}>{world.description}</Text>
                  )}
                </Table.Td>
                <Table.Td><Badge color={statusColor(world.status)}>{world.status}</Badge></Table.Td>
                <Table.Td><Text size="sm" c="dimmed">{formatDate(world.modified_at)}</Text></Table.Td>
                <Table.Td>
                  <Menu position="bottom-end" withArrow>
                    <Menu.Target>
                      <Button variant="subtle" size="compact-sm" px={4}><IconDots size={16} /></Button>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Item
                        leftSection={<IconEdit size={14} />}
                        onClick={() => { window.location.href = `/admin/worlds/${world.id}/edit`; }}
                      >
                        Edit
                      </Menu.Item>
                      <Menu.Item
                        leftSection={<IconFileText size={14} />}
                        onClick={() => { window.location.href = `/admin/worlds/${world.id}/documents`; }}
                      >
                        Documents
                      </Menu.Item>
                      <Menu.Item
                        leftSection={<IconCopy size={14} />}
                        onClick={() => handleClone(world)}
                      >
                        Clone
                      </Menu.Item>
                      {isAdmin && (
                        <Menu.Item
                          color="red"
                          leftSection={<IconTrash size={14} />}
                          onClick={() => handleDelete(world)}
                        >
                          Delete
                        </Menu.Item>
                      )}
                    </Menu.Dropdown>
                  </Menu>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <CreateWorldModal opened={createOpen} onClose={() => setCreateOpen(false)} onSaved={refresh} />
    </Container>
  );
}
