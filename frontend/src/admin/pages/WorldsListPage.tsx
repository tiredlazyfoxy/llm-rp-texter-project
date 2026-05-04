import { Fragment, useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate } from "react-router-dom";
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
import { formatDate } from "../../utils/formatDate";
import type { WorldItem } from "../../types/world";
import {
  WorldsListPageState,
  loadWorlds,
  CreateWorldDraft,
  createNewWorld,
} from "./worldsListPageState";

// ---------------------------------------------------------------------------
// Create world modal
// ---------------------------------------------------------------------------

interface CreateWorldModalProps {
  opened: boolean;
  onClose: () => void;
  onCreated: (world: WorldItem) => void;
}

const CreateWorldModal = observer(function CreateWorldModal({
  opened,
  onClose,
  onCreated,
}: CreateWorldModalProps) {
  const [draft] = useState(() => new CreateWorldDraft());

  // Reset whenever the modal opens.
  useEffect(() => {
    if (opened) draft.reset();
  }, [opened, draft]);

  const handleSubmit = async () => {
    if (!draft.canSubmit) return;
    const ctrl = new AbortController();
    const created = await createNewWorld(draft, ctrl.signal);
    if (created) {
      onCreated(created);
      onClose();
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Create World">
      <Stack>
        {draft.saveError && <Alert color="red">{draft.saveError}</Alert>}
        <TextInput
          label="Name"
          value={draft.name}
          onChange={(e) => {
            draft.name = e.currentTarget.value;
            if (draft.serverErrors.name) {
              delete draft.serverErrors.name;
            }
          }}
          error={draft.errors.name}
          required
        />
        <Textarea
          label="Description"
          value={draft.description}
          onChange={(e) => { draft.description = e.currentTarget.value; }}
          minRows={3}
        />
        <Select
          label="Status"
          data={[
            { value: "draft", label: "Draft" },
            { value: "public", label: "Public" },
            { value: "private", label: "Private" },
            { value: "archived", label: "Archived" },
          ]}
          value={draft.status}
          onChange={(v) => { draft.status = v || "draft"; }}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            disabled={!draft.canSubmit}
            loading={draft.saveStatus === "loading"}
          >
            Create
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
});

// ---------------------------------------------------------------------------
// Status badge helper
// ---------------------------------------------------------------------------

function statusColor(s: string): string {
  if (s === "public") return "green";
  if (s === "private") return "yellow";
  if (s === "archived") return "gray";
  return "blue";
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export const WorldsListPage = observer(function WorldsListPage() {
  const [state] = useState(() => new WorldsListPageState());
  const [createOpen, setCreateOpen] = useState(false);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const ctrl = new AbortController();
    loadWorlds(state, ctrl.signal);
    return () => ctrl.abort();
  }, []);

  const handleCreated = () => {
    const ctrl = new AbortController();
    loadWorlds(state, ctrl.signal);
  };

  const loading = state.worldsStatus === "loading" || state.worldsStatus === "idle";

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>Worlds</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setCreateOpen(true)}>
          Create World
        </Button>
      </Group>

      {state.worldsError && (
        <Alert
          color="red"
          mb="md"
          withCloseButton
          onClose={() => { state.worldsError = null; }}
        >
          {state.worldsError}
        </Alert>
      )}

      {loading ? (
        <Group justify="center" py="xl"><Loader /></Group>
      ) : state.worlds.length === 0 ? (
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
            {state.worlds.map(world => {
              const hovered = hoveredId === world.id;
              const rowProps = {
                style: { cursor: "pointer", backgroundColor: hovered ? "var(--mantine-color-default-hover)" : undefined },
                onMouseEnter: () => setHoveredId(world.id),
                onMouseLeave: () => setHoveredId(null),
                onClick: () => navigate(`/worlds/${world.id}`),
              };
              return (
                <Fragment key={world.id}>
                  <Table.Tr {...rowProps}>
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
                    <Table.Tr {...rowProps}>
                      <Table.Td colSpan={3} pt={0} pb="xs">
                        <Text size="xs" c="dimmed" lineClamp={1}>{world.description}</Text>
                      </Table.Td>
                    </Table.Tr>
                  )}
                </Fragment>
              );
            })}
          </Table.Tbody>
        </Table>
      )}

      <CreateWorldModal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={handleCreated}
      />
    </Container>
  );
});
