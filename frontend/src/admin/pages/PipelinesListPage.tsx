import { useCallback, useEffect, useState } from "react";
import {
  ActionIcon,
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
import { IconPlus, IconTrash } from "@tabler/icons-react";
import { formatDate } from "../../utils/formatDate";
import { getCurrentUser } from "../../auth";
import type { CreatePipelineRequest, PipelineItem } from "../../types/pipeline";
import { createPipeline, deletePipeline, listPipelines } from "../../api/pipelines";

// ---------------------------------------------------------------------------
// Create pipeline modal
// ---------------------------------------------------------------------------

interface CreatePipelineModalProps {
  opened: boolean;
  onClose: () => void;
  onCreated: (pipeline: PipelineItem) => void;
}

function CreatePipelineModal({ opened, onClose, onCreated }: CreatePipelineModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState("simple");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (opened) {
      setName("");
      setDescription("");
      setKind("simple");
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
      const req: CreatePipelineRequest = {
        name: name.trim(),
        description: description.trim() || undefined,
        kind,
      };
      const created = await createPipeline(req);
      onCreated(created);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create pipeline");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Create Pipeline">
      <Stack>
        {error && <Alert color="red">{error}</Alert>}
        <TextInput
          label="Name"
          value={name}
          onChange={e => setName(e.currentTarget.value)}
          required
        />
        <Select
          label="Kind"
          data={[
            { value: "simple", label: "Simple" },
            { value: "chain", label: "Chain Pipeline" },
            { value: "agentic", label: "Agentic (coming soon)", disabled: true },
          ]}
          value={kind}
          onChange={v => setKind(v || "simple")}
        />
        <Textarea
          label="Description"
          value={description}
          onChange={e => setDescription(e.currentTarget.value)}
          minRows={3}
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
// Helpers
// ---------------------------------------------------------------------------

function kindColor(kind: string): string {
  if (kind === "chain") return "violet";
  if (kind === "agentic") return "orange";
  return "blue";
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function PipelinesListPage() {
  const [pipelines, setPipelines] = useState<PipelineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const isAdmin = getCurrentUser()?.role === "admin";

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPipelines(await listPipelines());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load pipelines");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleCreated = (pipeline: PipelineItem) => {
    window.location.href = `/admin/pipelines/${pipeline.id}`;
  };

  const handleDelete = async (pipeline: PipelineItem, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(`Delete pipeline "${pipeline.name}"?`)) return;
    try {
      await deletePipeline(pipeline.id);
      await refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (/referenced/i.test(msg)) {
        setError("This pipeline is referenced by one or more worlds — re-point them first.");
      } else {
        setError(msg);
      }
    }
  };

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>Pipelines</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setCreateOpen(true)}>
          Create Pipeline
        </Button>
      </Group>

      {error && (
        <Alert color="red" mb="md" withCloseButton onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Group justify="center" py="xl"><Loader /></Group>
      ) : pipelines.length === 0 ? (
        <Text c="dimmed" ta="center" py="xl">
          No pipelines yet. Create one to get started.
        </Text>
      ) : (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th style={{ width: 110 }}>Kind</Table.Th>
              <Table.Th>Description</Table.Th>
              <Table.Th style={{ width: 110 }}>Modified</Table.Th>
              <Table.Th style={{ width: 50 }} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {pipelines.map(p => {
              const hovered = hoveredId === p.id;
              const rowProps = {
                style: {
                  cursor: "pointer",
                  backgroundColor: hovered ? "var(--mantine-color-default-hover)" : undefined,
                },
                onMouseEnter: () => setHoveredId(p.id),
                onMouseLeave: () => setHoveredId(null),
                onClick: () => { window.location.href = `/admin/pipelines/${p.id}`; },
              };
              return (
                <Table.Tr key={p.id} {...rowProps}>
                  <Table.Td>
                    <Text fw={500}>{p.name}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="sm" color={kindColor(p.kind)} variant="light">{p.kind}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed" lineClamp={1}>{p.description}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">{formatDate(p.modified_at)}</Text>
                  </Table.Td>
                  <Table.Td>
                    {isAdmin && (
                      <ActionIcon
                        variant="subtle"
                        size="sm"
                        color="red"
                        onClick={(e) => handleDelete(p, e)}
                        title="Delete pipeline"
                      >
                        <IconTrash size={14} />
                      </ActionIcon>
                    )}
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}

      <CreatePipelineModal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={handleCreated}
      />
    </Container>
  );
}
