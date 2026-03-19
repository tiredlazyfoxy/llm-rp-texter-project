import { useCallback, useEffect, useState } from "react";
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
  clearEmbedding,
  createServer,
  deleteServer,
  listServers,
  probeModels,
  setEmbedding,
  setEnabledModels,
  updateServer,
} from "../../api/llmServers";

// ---------------------------------------------------------------------------
// Server form modal (create + edit)
// ---------------------------------------------------------------------------

const BACKEND_OPTIONS = [
  { value: "llama-swap", label: "llama-swap" },
  { value: "openai", label: "OpenAI-compatible" },
];

interface ServerFormModalProps {
  opened: boolean;
  server: LlmServerItem | null; // null = create mode
  onClose: () => void;
  onSaved: () => void;
  onModels?: (server: LlmServerItem) => void;
}

function ServerFormModal({ opened, server, onClose, onSaved, onModels }: ServerFormModalProps) {
  const isEdit = server !== null;

  const [name, setName] = useState("");
  const [backendType, setBackendType] = useState("openai");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (opened && server) {
      setName(server.name);
      setBackendType(server.backend_type);
      setBaseUrl(server.base_url);
      setApiKey("");
      setIsActive(server.is_active);
    } else if (opened) {
      setName("");
      setBackendType("openai");
      setBaseUrl("");
      setApiKey("");
      setIsActive(true);
    }
    setError(null);
    setLoading(false);
  }, [opened, server]);

  const handleClose = () => {
    onClose();
  };

  const handleSubmit = async () => {
    setError(null);
    if (!name.trim()) { setError("Name is required"); return; }
    if (!baseUrl.trim()) { setError("Base URL is required"); return; }

    setLoading(true);
    try {
      if (isEdit) {
        await updateServer(server.id, {
          name: name.trim(),
          backend_type: backendType,
          base_url: baseUrl.trim(),
          ...(apiKey ? { api_key: apiKey } : {}),
          is_active: isActive,
        });
      } else {
        await createServer({
          name: name.trim(),
          backend_type: backendType,
          base_url: baseUrl.trim(),
          api_key: apiKey || null,
          is_active: isActive,
        });
      }
      handleClose();
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={handleClose} title={isEdit ? "Edit Server" : "Add Server"} size="md">
      <Stack>
        {error && (
          <Alert color="red" withCloseButton onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <TextInput
          label="Name"
          placeholder="e.g. Local llama-swap"
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
        />
        <Select
          label="Backend Type"
          data={BACKEND_OPTIONS}
          value={backendType}
          onChange={(v) => v && setBackendType(v)}
        />
        <TextInput
          label="Base URL"
          placeholder="e.g. http://localhost:8080/v1"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.currentTarget.value)}
        />
        <PasswordInput
          label="API Key"
          placeholder={isEdit ? "(unchanged if empty)" : "(optional)"}
          description="Supports $ENV_VAR_NAME syntax"
          value={apiKey}
          onChange={(e) => setApiKey(e.currentTarget.value)}
        />
        <Switch
          label="Active"
          checked={isActive}
          onChange={(e) => setIsActive(e.currentTarget.checked)}
        />

        <Group justify="space-between">
          {isEdit && onModels ? (
            <Button
              variant="light"
              size="sm"
              leftSection={<IconList size={14} />}
              onClick={() => { handleClose(); onModels(server); }}
            >
              Select Models
            </Button>
          ) : <span />}
          <Button onClick={handleSubmit} loading={loading}>
            {isEdit ? "Save" : "Create"}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Models modal
// ---------------------------------------------------------------------------

interface ModelsModalProps {
  opened: boolean;
  server: LlmServerItem | null;
  onClose: () => void;
  onSaved: () => void;
}

function ModelsModal({ opened, server, onClose, onSaved }: ModelsModalProps) {
  const [available, setAvailable] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");
  const [probing, setProbing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!opened || !server) return;
    setFilter("");
    setError(null);
    setSaving(false);

    // Initialize selected from current enabled models
    setSelected(new Set(server.enabled_models));

    // Probe for available models
    setProbing(true);
    probeModels(server.id)
      .then((models) => {
        setAvailable(models);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to probe server");
        setAvailable([]);
      })
      .finally(() => setProbing(false));
  }, [opened, server]);

  if (!server) return null;

  // Union of probed + already enabled
  const allModels = Array.from(new Set([...available, ...server.enabled_models])).sort();
  const filtered = filter
    ? allModels.filter((m) => m.toLowerCase().includes(filter.toLowerCase()))
    : allModels;

  const toggleModel = (modelId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(modelId)) {
        next.delete(modelId);
      } else {
        next.add(modelId);
      }
      return next;
    });
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await setEnabledModels(server.id, Array.from(selected).sort());
      onClose();
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save models");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={`Models — ${server.name}`} size="md">
      <Stack>
        {error && (
          <Alert color="red" withCloseButton onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <TextInput
          placeholder="Filter models..."
          value={filter}
          onChange={(e) => setFilter(e.currentTarget.value)}
        />

        {probing ? (
          <Group justify="center" py="md"><Loader size="sm" /><Text size="sm" c="dimmed">Probing server...</Text></Group>
        ) : filtered.length === 0 ? (
          <Text size="sm" c="dimmed" ta="center" py="md">No models found</Text>
        ) : (
          <Stack gap={4} style={{ maxHeight: 400, overflowY: "auto" }}>
            {filtered.map((modelId) => (
              <Checkbox
                key={modelId}
                label={modelId}
                checked={selected.has(modelId)}
                onChange={() => toggleModel(modelId)}
              />
            ))}
          </Stack>
        )}

        <Group justify="space-between">
          <Text size="sm" c="dimmed">{selected.size} selected</Text>
          <Button onClick={handleSave} loading={saving}>
            Save
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Embedding modal (single model selection)
// ---------------------------------------------------------------------------

interface EmbeddingModalProps {
  opened: boolean;
  server: LlmServerItem | null;
  onClose: () => void;
  onSaved: () => void;
}

function EmbeddingModal({ opened, server, onClose, onSaved }: EmbeddingModalProps) {
  const [available, setAvailable] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [probing, setProbing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!opened || !server) return;
    setFilter("");
    setError(null);
    setSaving(false);
    setSelected(server.embedding_model);

    setProbing(true);
    probeModels(server.id)
      .then((models) => setAvailable(models))
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to probe server");
        setAvailable([]);
      })
      .finally(() => setProbing(false));
  }, [opened, server]);

  if (!server) return null;

  const filtered = filter
    ? available.filter((m) => m.toLowerCase().includes(filter.toLowerCase()))
    : available;

  const handleSave = async () => {
    if (!selected) { setError("Select an embedding model"); return; }
    setSaving(true);
    setError(null);
    try {
      await setEmbedding(server.id, selected);
      onClose();
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to set embedding");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={`Set Embedding — ${server.name}`} size="md">
      <Stack>
        {error && (
          <Alert color="red" withCloseButton onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <TextInput
          placeholder="Filter models..."
          value={filter}
          onChange={(e) => setFilter(e.currentTarget.value)}
        />

        {probing ? (
          <Group justify="center" py="md"><Loader size="sm" /><Text size="sm" c="dimmed">Probing server...</Text></Group>
        ) : filtered.length === 0 ? (
          <Text size="sm" c="dimmed" ta="center" py="md">No models found</Text>
        ) : (
          <Radio.Group value={selected ?? ""} onChange={setSelected}>
            <Stack gap={4} style={{ maxHeight: 400, overflowY: "auto" }}>
              {filtered.map((modelId) => (
                <Radio key={modelId} value={modelId} label={modelId} />
              ))}
            </Stack>
          </Radio.Group>
        )}

        <Group justify="flex-end">
          <Button onClick={handleSave} loading={saving} disabled={!selected}>
            Set Embedding
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function LlmServersPage() {
  const [servers, setServers] = useState<LlmServerItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form modal state
  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<LlmServerItem | null>(null);

  // Models modal state
  const [modelsTarget, setModelsTarget] = useState<LlmServerItem | null>(null);

  // Embedding modal state
  const [embeddingTarget, setEmbeddingTarget] = useState<LlmServerItem | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setServers(await listServers());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load servers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleCreate = () => {
    setEditTarget(null);
    setFormOpen(true);
  };

  const handleEdit = (server: LlmServerItem) => {
    setEditTarget(server);
    setFormOpen(true);
  };

  const handleDelete = async (server: LlmServerItem) => {
    if (!window.confirm(`Delete server "${server.name}"? This cannot be undone.`)) return;
    try {
      await deleteServer(server.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete server");
    }
  };

  const handleModels = (server: LlmServerItem) => {
    setModelsTarget(server);
  };

  const handleClearEmbedding = async (server: LlmServerItem) => {
    if (!window.confirm(`Remove embedding designation from "${server.name}"?`)) return;
    try {
      await clearEmbedding();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to clear embedding");
    }
  };

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>LLM Servers</Title>
        <Button leftSection={<IconPlus size={16} />} size="sm" onClick={handleCreate}>
          Add Server
        </Button>
      </Group>

      {error && (
        <Alert color="red" mb="md" withCloseButton onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Group justify="center" py="xl"><Loader /></Group>
      ) : servers.length === 0 ? (
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
            {servers.map((server) => (
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
                        onClick={() => handleModels(server)}
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
        onModels={handleModels}
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
}
