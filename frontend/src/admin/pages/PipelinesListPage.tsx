import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate } from "react-router-dom";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { IconPlus, IconTrash } from "@tabler/icons-react";
import { formatDate } from "../../utils/formatDate";
import { getCurrentUser } from "../../auth";
import type { PipelineItem } from "../../types/pipeline";
import {
  PipelinesListPageState,
  deletePipeline,
  loadPipelines,
} from "./pipelinesListPageState";

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

export const PipelinesListPage = observer(function PipelinesListPage() {
  const [state] = useState(() => new PipelinesListPageState());
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const ctrl = new AbortController();
    void loadPipelines(state, ctrl.signal);
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isAdmin = getCurrentUser()?.role === "admin";

  const handleDelete = async (pipeline: PipelineItem, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(`Delete pipeline "${pipeline.name}"?`)) return;
    const ctrl = new AbortController();
    await deletePipeline(state, pipeline.id, ctrl.signal);
  };

  const loading =
    state.pipelinesStatus === "loading" || state.pipelinesStatus === "idle";

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>Pipelines</Title>
        <Button
          leftSection={<IconPlus size={16} />}
          onClick={() => navigate("/pipelines/new")}
        >
          Create Pipeline
        </Button>
      </Group>

      {state.pipelinesError && (
        <Alert
          color="red"
          mb="md"
          withCloseButton
          onClose={() => { state.pipelinesError = null; }}
        >
          {state.pipelinesError}
        </Alert>
      )}

      {loading ? (
        <Group justify="center" py="xl"><Loader /></Group>
      ) : state.pipelines.length === 0 ? (
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
            {state.pipelines.map((p) => {
              const hovered = hoveredId === p.id;
              const rowProps = {
                style: {
                  cursor: "pointer",
                  backgroundColor: hovered ? "var(--mantine-color-default-hover)" : undefined,
                },
                onMouseEnter: () => setHoveredId(p.id),
                onMouseLeave: () => setHoveredId(null),
                onClick: () => navigate(`/pipelines/${p.id}`),
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
    </Container>
  );
});
