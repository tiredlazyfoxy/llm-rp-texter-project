import { useCallback, useEffect, useState } from "react";
import { formatDate } from "../../utils/formatDate";
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Modal,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { IconPlus } from "@tabler/icons-react";
import type { WorldItem } from "../../types/world";
import { createWorld, listWorlds } from "../../api/worlds";

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

// formatDate imported from utils

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function WorldsListPage() {
  const [worlds, setWorlds] = useState<WorldItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [hoveredId, setHoveredId] = useState<number | null>(null);

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
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th style={{ width: 90 }}>Status</Table.Th>
              <Table.Th style={{ width: 110 }}>Modified</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {worlds.map(world => {
              const hovered = hoveredId === world.id;
              const rowProps = {
                style: { cursor: "pointer", backgroundColor: hovered ? "var(--mantine-color-default-hover)" : undefined },
                onMouseEnter: () => setHoveredId(world.id),
                onMouseLeave: () => setHoveredId(null),
                onClick: () => { window.location.href = `/admin/worlds/${world.id}`; },
              };
              return (
                <>
                  <Table.Tr key={world.id} {...rowProps}>
                    <Table.Td pb={world.description ? 2 : undefined}>
                      <Text fw={500}>{world.name}</Text>
                    </Table.Td>
                    <Table.Td pb={world.description ? 2 : undefined} style={{ width: 90 }}>
                      <Badge color={statusColor(world.status)} variant="light">{world.status}</Badge>
                    </Table.Td>
                    <Table.Td pb={world.description ? 2 : undefined} style={{ width: 110 }}>
                      <Text size="sm" c="dimmed">{formatDate(world.modified_at)}</Text>
                    </Table.Td>
                  </Table.Tr>
                  {world.description && (
                    <Table.Tr key={world.id + "_desc"} {...rowProps}>
                      <Table.Td colSpan={3} pt={0} pb="xs">
                        <Text size="xs" c="dimmed" lineClamp={1}>{world.description}</Text>
                      </Table.Td>
                    </Table.Tr>
                  )}
                </>
              );
            })}
          </Table.Tbody>
        </Table>
      )}

      <CreateWorldModal opened={createOpen} onClose={() => setCreateOpen(false)} onSaved={refresh} />
    </Container>
  );
}
