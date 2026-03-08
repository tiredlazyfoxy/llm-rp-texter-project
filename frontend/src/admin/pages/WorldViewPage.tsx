import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Menu,
  Modal,
  Paper,
  Select,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import {
  IconArrowLeft,
  IconDots,
  IconDownload,
  IconEdit,
  IconPlus,
  IconRefresh,
  IconTrash,
  IconUpload,
} from "@tabler/icons-react";
import type { DocumentItem, WorldDetail } from "../../types/world";
import {
  createDocument,
  deleteDocument,
  downloadAllDocuments,
  downloadDocument,
  getWorld,
  listDocuments,
  reindexWorld,
  uploadDocuments,
} from "../../api/worlds";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractWorldId(): string | null {
  const m = window.location.pathname.match(/\/admin\/worlds\/(\d+)(?:\/|$)/);
  return m ? m[1] : null;
}

const DOC_TYPE_LABELS: Record<string, string> = {
  location: "Location",
  npc: "NPC",
  lore_fact: "Lore Fact",
};

function docTypeBadgeColor(dt: string): string {
  if (dt === "location") return "teal";
  if (dt === "npc") return "violet";
  return "orange";
}

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

function docDisplayName(doc: DocumentItem): string {
  if (doc.name) return doc.name;
  if (doc.doc_type === "lore_fact") {
    return doc.content.slice(0, 60) + (doc.content.length > 60 ? "..." : "");
  }
  return "(untitled)";
}

// ---------------------------------------------------------------------------
// Create document modal
// ---------------------------------------------------------------------------

interface CreateDocModalProps {
  opened: boolean;
  worldId: string;
  initialDocType?: string;
  onClose: () => void;
  onSaved: () => void;
}

function CreateDocModal({ opened, worldId, initialDocType, onClose, onSaved }: CreateDocModalProps) {
  const [docType, setDocType] = useState("location");
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (opened) {
      setDocType(initialDocType || "location");
      setName("");
      setContent("");
      setError(null);
    }
  }, [opened]);

  const handleSubmit = async () => {
    if (docType !== "lore_fact" && !name.trim()) {
      setError("Name is required");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await createDocument(worldId, {
        doc_type: docType,
        name: docType !== "lore_fact" ? name.trim() : undefined,
        content,
      });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create document");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Create Document" size="lg">
      <Stack>
        {error && <Alert color="red">{error}</Alert>}
        <Select
          label="Type"
          data={[
            { value: "location", label: "Location" },
            { value: "npc", label: "NPC" },
            { value: "lore_fact", label: "Lore Fact" },
          ]}
          value={docType}
          onChange={v => setDocType(v || "location")}
        />
        {docType !== "lore_fact" && (
          <TextInput label="Name" value={name} onChange={e => setName(e.currentTarget.value)} required />
        )}
        <Textarea label="Content" value={content} onChange={e => setContent(e.currentTarget.value)} minRows={6} autosize maxRows={16} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} loading={loading}>Create</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Info tab content
// ---------------------------------------------------------------------------

function InfoTab({ world, worldId }: { world: WorldDetail; worldId: string }) {
  return (
    <Stack>
      <Group justify="flex-end">
        <Button leftSection={<IconEdit size={16} />} onClick={() => { window.location.href = `/admin/worlds/${worldId}/edit`; }}>
          Edit World
        </Button>
      </Group>

      <Paper p="md" withBorder>
        <Stack gap="sm">
          <Group>
            <Text fw={600} w={120}>Status</Text>
            <Badge color={statusColor(world.status)}>{world.status}</Badge>
          </Group>
          <Group align="flex-start">
            <Text fw={600} w={120}>Description</Text>
            <Text style={{ flex: 1 }}>{world.description || <Text span c="dimmed">-</Text>}</Text>
          </Group>
          <Group align="flex-start">
            <Text fw={600} w={120}>Lore</Text>
            <Text style={{ flex: 1, whiteSpace: "pre-wrap" }} lineClamp={10}>{world.lore || <Text span c="dimmed">-</Text>}</Text>
          </Group>
        </Stack>
      </Paper>

      <Group grow>
        <Paper p="md" withBorder ta="center">
          <Text size="xl" fw={700}>{world.location_count}</Text>
          <Text size="sm" c="dimmed">Locations</Text>
        </Paper>
        <Paper p="md" withBorder ta="center">
          <Text size="xl" fw={700}>{world.npc_count}</Text>
          <Text size="sm" c="dimmed">NPCs</Text>
        </Paper>
        <Paper p="md" withBorder ta="center">
          <Text size="xl" fw={700}>{world.lore_fact_count}</Text>
          <Text size="sm" c="dimmed">Lore Facts</Text>
        </Paper>
      </Group>

      {world.stats.length > 0 && (
        <Paper p="md" withBorder>
          <Title order={5} mb="xs">Stats ({world.stats.length})</Title>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Scope</Table.Th>
                <Table.Th>Type</Table.Th>
                <Table.Th>Default</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {world.stats.map(s => (
                <Table.Tr key={s.id}>
                  <Table.Td><Text size="sm" fw={500}>{s.name}</Text></Table.Td>
                  <Table.Td><Badge size="sm" variant="light">{s.scope}</Badge></Table.Td>
                  <Table.Td><Badge size="sm" variant="outline">{s.stat_type}</Badge></Table.Td>
                  <Table.Td><Text size="sm">{s.default_value}</Text></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}

      {world.rules.length > 0 && (
        <Paper p="md" withBorder>
          <Title order={5} mb="xs">Rules ({world.rules.length})</Title>
          <Stack gap="xs">
            {world.rules.map((r, idx) => (
              <Group key={r.id} gap="xs" wrap="nowrap">
                <Badge size="sm" variant="light" circle>{idx + 1}</Badge>
                <Text size="sm">{r.rule_text}</Text>
              </Group>
            ))}
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Documents tab content
// ---------------------------------------------------------------------------

interface DocsTabProps {
  worldId: string;
  docTypeFilter?: string;
}

function DocsTab({ worldId, docTypeFilter }: DocsTabProps) {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadType, setUploadType] = useState("location");
  const [reindexing, setReindexing] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDocs(await listDocuments(worldId, docTypeFilter));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [worldId, docTypeFilter]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleDelete = async (doc: DocumentItem) => {
    if (!window.confirm(`Delete "${docDisplayName(doc)}"?`)) return;
    try {
      await deleteDocument(worldId, doc.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete document");
    }
  };

  const handleDownload = async (doc: DocumentItem) => {
    try {
      await downloadDocument(worldId, doc.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to download document");
    }
  };

  const handleDownloadAll = async () => {
    try {
      await downloadAllDocuments(worldId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to download documents");
    }
  };

  const handleUploadClick = (type: string) => {
    setUploadType(type);
    fileInputRef.current?.click();
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    try {
      await uploadDocuments(worldId, Array.from(files), uploadType);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    }
    e.target.value = "";
  };

  const handleReindex = async () => {
    setReindexing(true);
    setError(null);
    try {
      const result = await reindexWorld(worldId);
      if (result.warning) {
        setError(result.warning);
      } else {
        setError(null);
        window.alert(`Reindexed ${result.indexed_count} documents.`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reindex failed");
    } finally {
      setReindexing(false);
    }
  };

  return (
    <Stack>
      <Group justify="flex-end">
        <Button variant="light" leftSection={<IconRefresh size={16} />} onClick={handleReindex} loading={reindexing}>
          Reindex
        </Button>
        <Menu position="bottom-end" withArrow>
          <Menu.Target>
            <Button variant="light" leftSection={<IconUpload size={16} />}>Upload</Button>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item onClick={() => handleUploadClick("location")}>Upload Locations</Menu.Item>
            <Menu.Item onClick={() => handleUploadClick("npc")}>Upload NPCs</Menu.Item>
          </Menu.Dropdown>
        </Menu>
        <Button variant="light" leftSection={<IconDownload size={16} />} onClick={handleDownloadAll}>
          Download All
        </Button>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setCreateOpen(true)}>
          Create
        </Button>
      </Group>

      <input ref={fileInputRef} type="file" accept=".md,.txt" multiple style={{ display: "none" }} onChange={handleFileUpload} />

      {error && <Alert color="red" mb="md" withCloseButton onClose={() => setError(null)}>{error}</Alert>}

      {loading ? (
        <Group justify="center" py="xl"><Loader /></Group>
      ) : docs.length === 0 ? (
        <Text c="dimmed" ta="center" py="xl">No documents yet.</Text>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              {!docTypeFilter && <Table.Th>Type</Table.Th>}
              <Table.Th>Modified</Table.Th>
              <Table.Th w={60} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {docs.map(doc => (
              <Table.Tr key={doc.id}>
                <Table.Td>
                  <Text size="sm" fw={500} lineClamp={1}>{docDisplayName(doc)}</Text>
                </Table.Td>
                {!docTypeFilter && (
                  <Table.Td>
                    <Badge size="sm" color={docTypeBadgeColor(doc.doc_type)}>
                      {DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
                    </Badge>
                  </Table.Td>
                )}
                <Table.Td><Text size="sm" c="dimmed">{formatDate(doc.modified_at)}</Text></Table.Td>
                <Table.Td>
                  <Menu position="bottom-end" withArrow>
                    <Menu.Target>
                      <Button variant="subtle" size="compact-sm" px={4}><IconDots size={16} /></Button>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Item
                        leftSection={<IconEdit size={14} />}
                        onClick={() => { window.location.href = `/admin/worlds/${worldId}/documents/${doc.id}/edit`; }}
                      >
                        Edit
                      </Menu.Item>
                      <Menu.Item leftSection={<IconDownload size={14} />} onClick={() => handleDownload(doc)}>
                        Download
                      </Menu.Item>
                      <Menu.Item color="red" leftSection={<IconTrash size={14} />} onClick={() => handleDelete(doc)}>
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

      <CreateDocModal
        opened={createOpen}
        worldId={worldId}
        initialDocType={docTypeFilter}
        onClose={() => setCreateOpen(false)}
        onSaved={refresh}
      />
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Chats tab content (placeholder)
// ---------------------------------------------------------------------------

function ChatsTab() {
  return (
    <Text c="dimmed" ta="center" py="xl">
      No chats yet — chats will appear here once the chat system is implemented.
    </Text>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function WorldViewPage() {
  const worldId = extractWorldId();
  const [world, setWorld] = useState<WorldDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string | null>("info");

  useEffect(() => {
    if (!worldId) return;
    setLoading(true);
    setError(null);
    getWorld(worldId)
      .then(setWorld)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load world"))
      .finally(() => setLoading(false));
  }, [worldId]);

  if (!worldId) return <Container py="md"><Alert color="red">Invalid world ID</Alert></Container>;
  if (loading) return <Container py="md"><Group justify="center" py="xl"><Loader /></Group></Container>;
  if (error) return <Container py="md"><Alert color="red">{error}</Alert></Container>;
  if (!world) return null;

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Group>
          <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => { window.location.href = "/admin/worlds"; }}>
            Back
          </Button>
          <Title order={3}>{world.name}</Title>
          <Badge color={statusColor(world.status)}>{world.status}</Badge>
        </Group>
      </Group>

      <Tabs value={activeTab} onChange={setActiveTab}>
        <Tabs.List mb="md">
          <Tabs.Tab value="info">Info</Tabs.Tab>
          <Tabs.Tab value="all">All Docs</Tabs.Tab>
          <Tabs.Tab value="location">Locations</Tabs.Tab>
          <Tabs.Tab value="npc">NPCs</Tabs.Tab>
          <Tabs.Tab value="lore_fact">Lore Facts</Tabs.Tab>
          <Tabs.Tab value="chats">Chats</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="info">
          <InfoTab world={world} worldId={worldId} />
        </Tabs.Panel>

        <Tabs.Panel value="all">
          <DocsTab worldId={worldId} />
        </Tabs.Panel>

        <Tabs.Panel value="location">
          <DocsTab worldId={worldId} docTypeFilter="location" />
        </Tabs.Panel>

        <Tabs.Panel value="npc">
          <DocsTab worldId={worldId} docTypeFilter="npc" />
        </Tabs.Panel>

        <Tabs.Panel value="lore_fact">
          <DocsTab worldId={worldId} docTypeFilter="lore_fact" />
        </Tabs.Panel>

        <Tabs.Panel value="chats">
          <ChatsTab />
        </Tabs.Panel>
      </Tabs>
    </Container>
  );
}
