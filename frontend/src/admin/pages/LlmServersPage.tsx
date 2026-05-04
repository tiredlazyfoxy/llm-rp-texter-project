import { useEffect, useState } from "react";
import { makeAutoObservable, runInAction } from "mobx";
import { observer } from "mobx-react-lite";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  Container,
  Group,
  Loader,
  Menu,
  Modal,
  PasswordInput,
  Radio,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import {
  IconBrain,
  IconDots,
  IconEdit,
  IconList,
  IconPlus,
  IconTrash,
} from "@tabler/icons-react";
import type { LlmServerItem } from "../../types/llmServer";
import {
  createServer,
  probeModels,
  setEmbedding,
  setEnabledModels,
  updateServer,
} from "../../api/llmServers";
import {
  LlmServersPageState,
  clearEmbeddingAction,
  clearServersError,
  deleteServerAction,
  loadServers,
} from "./llmServersPageState";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

const BACKEND_OPTIONS = [
  { value: "llama-swap", label: "llama-swap" },
  { value: "openai", label: "OpenAI-compatible" },
];

// ---------------------------------------------------------------------------
// Server form modal — component-local draft
// ---------------------------------------------------------------------------

class ServerFormDraft {
  name = "";
  backendType = "openai";
  baseUrl = "";
  apiKey = "";
  isActive = true;

  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  loadFrom(server: LlmServerItem | null): void {
    if (server) {
      this.name = server.name;
      this.backendType = server.backend_type;
      this.baseUrl = server.base_url;
      this.apiKey = "";
      this.isActive = server.is_active;
    } else {
      this.name = "";
      this.backendType = "openai";
      this.baseUrl = "";
      this.apiKey = "";
      this.isActive = true;
    }
    this.saveStatus = "idle";
    this.saveError = null;
  }

  get errors(): { name?: string; baseUrl?: string } {
    const e: { name?: string; baseUrl?: string } = {};
    if (!this.name.trim()) e.name = "Name is required";
    if (!this.baseUrl.trim()) e.baseUrl = "Base URL is required";
    return e;
  }

  get isValid(): boolean {
    return Object.keys(this.errors).length === 0;
  }

  get canSubmit(): boolean {
    return this.isValid && this.saveStatus !== "loading";
  }
}

function clearServerFormError(draft: ServerFormDraft): void {
  draft.saveError = null;
}

async function submitServerForm(
  draft: ServerFormDraft,
  serverId: string | null,
  signal: AbortSignal,
): Promise<LlmServerItem | null> {
  if (!draft.canSubmit) return null;
  draft.saveStatus = "loading";
  draft.saveError = null;
  try {
    let saved: LlmServerItem;
    if (serverId !== null) {
      saved = await updateServer(
        serverId,
        {
          name: draft.name.trim(),
          backend_type: draft.backendType,
          base_url: draft.baseUrl.trim(),
          ...(draft.apiKey ? { api_key: draft.apiKey } : {}),
          is_active: draft.isActive,
        },
        signal,
      );
    } else {
      saved = await createServer(
        {
          name: draft.name.trim(),
          backend_type: draft.backendType,
          base_url: draft.baseUrl.trim(),
          api_key: draft.apiKey || null,
          is_active: draft.isActive,
        },
        signal,
      );
    }
    runInAction(() => {
      draft.saveStatus = "ready";
    });
    return saved;
  } catch (err) {
    if (signal.aborted) return null;
    runInAction(() => {
      draft.saveStatus = "error";
      draft.saveError = err instanceof Error ? err.message : "Failed to save server";
    });
    return null;
  }
}

interface ServerFormModalProps {
  opened: boolean;
  server: LlmServerItem | null; // null = create mode
  onClose: () => void;
  onSaved: () => void;
  onModels?: (server: LlmServerItem) => void;
}

const ServerFormModal = observer(function ServerFormModal({
  opened,
  server,
  onClose,
  onSaved,
  onModels,
}: ServerFormModalProps) {
  const [draft] = useState(() => new ServerFormDraft());
  const isEdit = server !== null;

  useEffect(() => {
    if (opened) draft.loadFrom(server);
  }, [opened, server, draft]);

  const handleSubmit = async () => {
    if (!draft.canSubmit) return;
    const ctrl = new AbortController();
    const saved = await submitServerForm(draft, server?.id ?? null, ctrl.signal);
    if (saved) {
      onSaved();
      onClose();
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={isEdit ? "Edit Server" : "Add Server"} size="md">
      <Stack>
        {draft.saveError && (
          <Alert color="red" withCloseButton onClose={() => clearServerFormError(draft)}>
            {draft.saveError}
          </Alert>
        )}

        <TextInput
          label="Name"
          placeholder="e.g. Local llama-swap"
          value={draft.name}
          onChange={(e) => { draft.name = e.currentTarget.value; }}
          error={draft.errors.name}
        />
        <Select
          label="Backend Type"
          data={BACKEND_OPTIONS}
          value={draft.backendType}
          onChange={(v) => { if (v) draft.backendType = v; }}
        />
        <TextInput
          label="Base URL"
          placeholder="e.g. http://localhost:8080/v1"
          value={draft.baseUrl}
          onChange={(e) => { draft.baseUrl = e.currentTarget.value; }}
          error={draft.errors.baseUrl}
        />
        <PasswordInput
          label="API Key"
          placeholder={isEdit ? "(unchanged if empty)" : "(optional)"}
          description="Supports $ENV_VAR_NAME syntax"
          value={draft.apiKey}
          onChange={(e) => { draft.apiKey = e.currentTarget.value; }}
        />
        <Switch
          label="Active"
          checked={draft.isActive}
          onChange={(e) => { draft.isActive = e.currentTarget.checked; }}
        />

        <Group justify="space-between">
          {isEdit && server && onModels ? (
            <Button
              variant="light"
              size="sm"
              leftSection={<IconList size={14} />}
              onClick={() => { onClose(); onModels(server); }}
            >
              Select Models
            </Button>
          ) : <span />}
          <Button
            onClick={handleSubmit}
            disabled={!draft.canSubmit}
            loading={draft.saveStatus === "loading"}
          >
            {isEdit ? "Save" : "Create"}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
});

// ---------------------------------------------------------------------------
// Models modal — component-local draft (probe + multi-select)
// ---------------------------------------------------------------------------

class ModelsModalDraft {
  available: string[] = [];
  selected: Set<string> = new Set();
  filter = "";

  probeStatus: AsyncStatus = "idle";
  probeError: string | null = null;

  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  reset(initialSelected: string[]): void {
    this.available = [];
    this.selected = new Set(initialSelected);
    this.filter = "";
    this.probeStatus = "idle";
    this.probeError = null;
    this.saveStatus = "idle";
    this.saveError = null;
  }

  toggle(modelId: string): void {
    const next = new Set(this.selected);
    if (next.has(modelId)) next.delete(modelId);
    else next.add(modelId);
    this.selected = next;
  }
}

function clearModelsModalSaveError(draft: ModelsModalDraft): void {
  draft.saveError = null;
}

async function probeModelsAction(
  draft: ModelsModalDraft,
  serverId: string,
  signal: AbortSignal,
): Promise<void> {
  draft.probeStatus = "loading";
  draft.probeError = null;
  try {
    const models = await probeModels(serverId, signal);
    runInAction(() => {
      draft.available = models;
      draft.probeStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      draft.available = [];
      draft.probeStatus = "error";
      draft.probeError = err instanceof Error ? err.message : "Failed to probe server";
    });
  }
}

async function submitEnabledModels(
  draft: ModelsModalDraft,
  serverId: string,
  signal: AbortSignal,
): Promise<boolean> {
  draft.saveStatus = "loading";
  draft.saveError = null;
  try {
    await setEnabledModels(serverId, Array.from(draft.selected).sort(), signal);
    runInAction(() => {
      draft.saveStatus = "ready";
    });
    return true;
  } catch (err) {
    if (signal.aborted) return false;
    runInAction(() => {
      draft.saveStatus = "error";
      draft.saveError = err instanceof Error ? err.message : "Failed to save models";
    });
    return false;
  }
}

interface ModelsModalProps {
  opened: boolean;
  server: LlmServerItem | null;
  onClose: () => void;
  onSaved: () => void;
}

const ModelsModal = observer(function ModelsModal({
  opened,
  server,
  onClose,
  onSaved,
}: ModelsModalProps) {
  const [draft] = useState(() => new ModelsModalDraft());

  useEffect(() => {
    if (!opened || !server) return;
    draft.reset(server.enabled_models);
    const ctrl = new AbortController();
    void probeModelsAction(draft, server.id, ctrl.signal);
    return () => ctrl.abort();
  }, [opened, server, draft]);

  if (!server) return null;

  // Union of probed + already enabled
  const allModels = Array.from(new Set([...draft.available, ...server.enabled_models])).sort();
  const filtered = draft.filter
    ? allModels.filter((m) => m.toLowerCase().includes(draft.filter.toLowerCase()))
    : allModels;

  const handleSave = async () => {
    const ctrl = new AbortController();
    const ok = await submitEnabledModels(draft, server.id, ctrl.signal);
    if (ok) {
      onSaved();
      onClose();
    }
  };

  const error = draft.probeError ?? draft.saveError;

  return (
    <Modal opened={opened} onClose={onClose} title={`Models — ${server.name}`} size="md">
      <Stack>
        {error && (
          <Alert color="red" withCloseButton onClose={() => clearModelsModalSaveError(draft)}>
            {error}
          </Alert>
        )}

        <TextInput
          placeholder="Filter models..."
          value={draft.filter}
          onChange={(e) => { draft.filter = e.currentTarget.value; }}
        />

        {draft.probeStatus === "loading" ? (
          <Group justify="center" py="md"><Loader size="sm" /><Text size="sm" c="dimmed">Probing server...</Text></Group>
        ) : filtered.length === 0 ? (
          <Text size="sm" c="dimmed" ta="center" py="md">No models found</Text>
        ) : (
          <Stack gap={4} style={{ maxHeight: 400, overflowY: "auto" }}>
            {filtered.map((modelId) => (
              <Checkbox
                key={modelId}
                label={modelId}
                checked={draft.selected.has(modelId)}
                onChange={() => draft.toggle(modelId)}
              />
            ))}
          </Stack>
        )}

        <Group justify="space-between">
          <Text size="sm" c="dimmed">{draft.selected.size} selected</Text>
          <Button onClick={handleSave} loading={draft.saveStatus === "loading"}>
            Save
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
});

// ---------------------------------------------------------------------------
// Embedding modal — component-local draft (single-model radio pick)
// ---------------------------------------------------------------------------

class EmbeddingModalDraft {
  available: string[] = [];
  selected: string | null = null;
  filter = "";

  probeStatus: AsyncStatus = "idle";
  probeError: string | null = null;

  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  reset(initialSelected: string | null): void {
    this.available = [];
    this.selected = initialSelected;
    this.filter = "";
    this.probeStatus = "idle";
    this.probeError = null;
    this.saveStatus = "idle";
    this.saveError = null;
  }

  get canSubmit(): boolean {
    return this.selected !== null && this.saveStatus !== "loading";
  }
}

function clearEmbeddingModalSaveError(draft: EmbeddingModalDraft): void {
  draft.saveError = null;
}

async function probeEmbeddingModels(
  draft: EmbeddingModalDraft,
  serverId: string,
  signal: AbortSignal,
): Promise<void> {
  draft.probeStatus = "loading";
  draft.probeError = null;
  try {
    const models = await probeModels(serverId, signal);
    runInAction(() => {
      draft.available = models;
      draft.probeStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      draft.available = [];
      draft.probeStatus = "error";
      draft.probeError = err instanceof Error ? err.message : "Failed to probe server";
    });
  }
}

async function submitEmbedding(
  draft: EmbeddingModalDraft,
  serverId: string,
  signal: AbortSignal,
): Promise<boolean> {
  if (!draft.canSubmit || draft.selected === null) return false;
  draft.saveStatus = "loading";
  draft.saveError = null;
  try {
    await setEmbedding(serverId, draft.selected, signal);
    runInAction(() => {
      draft.saveStatus = "ready";
    });
    return true;
  } catch (err) {
    if (signal.aborted) return false;
    runInAction(() => {
      draft.saveStatus = "error";
      draft.saveError = err instanceof Error ? err.message : "Failed to set embedding";
    });
    return false;
  }
}

interface EmbeddingModalProps {
  opened: boolean;
  server: LlmServerItem | null;
  onClose: () => void;
  onSaved: () => void;
}

const EmbeddingModal = observer(function EmbeddingModal({
  opened,
  server,
  onClose,
  onSaved,
}: EmbeddingModalProps) {
  const [draft] = useState(() => new EmbeddingModalDraft());

  useEffect(() => {
    if (!opened || !server) return;
    draft.reset(server.embedding_model);
    const ctrl = new AbortController();
    void probeEmbeddingModels(draft, server.id, ctrl.signal);
    return () => ctrl.abort();
  }, [opened, server, draft]);

  if (!server) return null;

  const filtered = draft.filter
    ? draft.available.filter((m) => m.toLowerCase().includes(draft.filter.toLowerCase()))
    : draft.available;

  const handleSave = async () => {
    if (!draft.canSubmit) return;
    const ctrl = new AbortController();
    const ok = await submitEmbedding(draft, server.id, ctrl.signal);
    if (ok) {
      onSaved();
      onClose();
    }
  };

  const error = draft.probeError ?? draft.saveError;

  return (
    <Modal opened={opened} onClose={onClose} title={`Set Embedding — ${server.name}`} size="md">
      <Stack>
        {error && (
          <Alert color="red" withCloseButton onClose={() => clearEmbeddingModalSaveError(draft)}>
            {error}
          </Alert>
        )}

        <TextInput
          placeholder="Filter models..."
          value={draft.filter}
          onChange={(e) => { draft.filter = e.currentTarget.value; }}
        />

        {draft.probeStatus === "loading" ? (
          <Group justify="center" py="md"><Loader size="sm" /><Text size="sm" c="dimmed">Probing server...</Text></Group>
        ) : filtered.length === 0 ? (
          <Text size="sm" c="dimmed" ta="center" py="md">No models found</Text>
        ) : (
          <Radio.Group value={draft.selected ?? ""} onChange={(v) => { draft.selected = v || null; }}>
            <Stack gap={4} style={{ maxHeight: 400, overflowY: "auto" }}>
              {filtered.map((modelId) => (
                <Radio key={modelId} value={modelId} label={modelId} />
              ))}
            </Stack>
          </Radio.Group>
        )}

        <Group justify="flex-end">
          <Button
            onClick={handleSave}
            loading={draft.saveStatus === "loading"}
            disabled={!draft.canSubmit}
          >
            Set Embedding
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
});

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export const LlmServersPage = observer(function LlmServersPage() {
  const [state] = useState(() => new LlmServersPageState());

  // Component-local UI flags / modal targets — transient, not page data.
  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<LlmServerItem | null>(null);
  const [modelsTarget, setModelsTarget] = useState<LlmServerItem | null>(null);
  const [embeddingTarget, setEmbeddingTarget] = useState<LlmServerItem | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    void loadServers(state, ctrl.signal);
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refresh = () => {
    const ctrl = new AbortController();
    void loadServers(state, ctrl.signal);
  };

  const handleCreate = () => {
    setEditTarget(null);
    setFormOpen(true);
  };

  const handleEdit = (server: LlmServerItem) => {
    setEditTarget(server);
    setFormOpen(true);
  };

  const handleDelete = async (server: LlmServerItem) => {
    const ctrl = new AbortController();
    await deleteServerAction(state, server, ctrl.signal);
  };

  const handleClearEmbedding = async (server: LlmServerItem) => {
    const ctrl = new AbortController();
    await clearEmbeddingAction(state, server, ctrl.signal);
  };

  const loading = state.serversStatus === "loading" || state.serversStatus === "idle";

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>LLM Servers</Title>
        <Button leftSection={<IconPlus size={16} />} size="sm" onClick={handleCreate}>
          Add Server
        </Button>
      </Group>

      {state.serversError && (
        <Alert color="red" mb="md" withCloseButton onClose={() => clearServersError(state)}>
          {state.serversError}
        </Alert>
      )}

      {loading ? (
        <Group justify="center" py="xl"><Loader /></Group>
      ) : state.servers.length === 0 ? (
        <Text c="dimmed" ta="center" py="xl">No LLM servers configured yet.</Text>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Type</Table.Th>
              <Table.Th>Base URL</Table.Th>
              <Table.Th>Key</Table.Th>
              <Table.Th>Models</Table.Th>
              <Table.Th>Active</Table.Th>
              <Table.Th w={60} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {state.servers.map((server) => (
              <Table.Tr key={server.id} style={!server.is_active ? { opacity: 0.5 } : undefined}>
                <Table.Td>
                  <Group gap="xs">
                    <Text size="sm">{server.name}</Text>
                    {server.is_embedding && (
                      <Badge variant="light" size="xs" color="teal">
                        Embedding: {server.embedding_model}
                      </Badge>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" size="sm" color={server.backend_type === "openai" ? "blue" : "grape"}>
                    {server.backend_type}
                  </Badge>
                </Table.Td>
                <Table.Td><Text size="sm" c="dimmed" truncate="end" maw={250}>{server.base_url}</Text></Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">{server.has_api_key ? "Yes" : "No"}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">{server.enabled_models.length}</Text>
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" size="sm" color={server.is_active ? "green" : "gray"}>
                    {server.is_active ? "Active" : "Inactive"}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Menu shadow="md" width={200} position="bottom-end">
                    <Menu.Target>
                      <ActionIcon variant="subtle" color="gray" size="sm">
                        <IconDots size={16} />
                      </ActionIcon>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Item
                        leftSection={<IconList size={14} />}
                        onClick={() => setModelsTarget(server)}
                      >
                        Models
                      </Menu.Item>
                      {server.is_embedding ? (
                        <Menu.Item
                            color="orange"
                          leftSection={<IconBrain size={14} />}
                          onClick={() => handleClearEmbedding(server)}
                        >
                          Clear Embedding
                        </Menu.Item>
                      ) : (
                        <Menu.Item
                          leftSection={<IconBrain size={14} />}
                          onClick={() => setEmbeddingTarget(server)}
                        >
                          Set as Embedding
                        </Menu.Item>
                      )}
                      <Menu.Item
                        leftSection={<IconEdit size={14} />}
                        onClick={() => handleEdit(server)}
                      >
                        Edit
                      </Menu.Item>
                      <Menu.Divider />
                      <Menu.Item
                        color="red"
                        leftSection={<IconTrash size={14} />}
                        onClick={() => handleDelete(server)}
                      >
                        Delete
                      </Menu.Item>
                    </Menu.Dropdown>
                  </Menu>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <ServerFormModal
        opened={formOpen}
        server={editTarget}
        onClose={() => setFormOpen(false)}
        onSaved={refresh}
        onModels={(s) => setModelsTarget(s)}
      />

      <ModelsModal
        opened={modelsTarget !== null}
        server={modelsTarget}
        onClose={() => setModelsTarget(null)}
        onSaved={refresh}
      />

      <EmbeddingModal
        opened={embeddingTarget !== null}
        server={embeddingTarget}
        onClose={() => setEmbeddingTarget(null)}
        onSaved={refresh}
      />
    </Container>
  );
});
