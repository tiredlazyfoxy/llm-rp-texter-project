import { useCallback, useEffect, useRef, useState } from "react";
import { formatDate } from "../../utils/formatDate";
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Menu,
  Paper,
  Stack,
  Table,
  Tabs,
  Text,
  Title,
} from "@mantine/core";
import {
  IconArrowLeft,
  IconDots,
  IconDownload,
  IconEdit,
  IconPin,
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

const TAB_SLUG_TO_VALUE: Record<string, string> = {
  "all-docs": "all",
  locations: "location",
  npcs: "npc",
  lore: "lore_fact",
  chats: "chats",
};

const TAB_VALUE_TO_SLUG: Record<string, string> = {
  all: "all-docs",
  location: "locations",
  npc: "npcs",
  lore_fact: "lore",
  chats: "chats",
};

function extractWorldId(): string | null {
  const m = window.location.pathname.match(/\/admin\/worlds\/(\d+)(?:\/|$)/);
  return m ? m[1] : null;
}

function extractTab(): string {
  const m = window.location.pathname.match(/\/admin\/worlds\/\d+\/([a-z-]+)$/);
  if (!m) return "info";
  return TAB_SLUG_TO_VALUE[m[1]] || "info";
}

function tabUrl(worldId: string, tab: string): string {
  const slug = TAB_VALUE_TO_SLUG[tab];
  return slug ? `/admin/worlds/${worldId}/${slug}` : `/admin/worlds/${worldId}`;
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

// formatDate imported from utils

function docDisplayName(doc: DocumentItem): string {
  if (doc.name) return doc.name;
  if (doc.doc_type === "lore_fact") {
    const firstLine = doc.content.split("\n", 1)[0];
    const headerMatch = firstLine.match(/^#+\s+(.+)/);
    if (headerMatch) return headerMatch[1];
    return firstLine.length > 80 ? firstLine.slice(0, 80) + "..." : firstLine;
  }
  return "(untitled)";
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
  refreshKey?: number;
}

function DocsTab({ worldId, docTypeFilter, refreshKey }: DocsTabProps) {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadType, setUploadType] = useState("location");
  const [reindexing, setReindexing] = useState(false);

  const refresh = useCallback(async (showLoader = true) => {
    if (showLoader) setLoading(true);
    setError(null);
    try {
      setDocs(await listDocuments(worldId, docTypeFilter));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load documents");
    } finally {
      if (showLoader) setLoading(false);
    }
  }, [worldId, docTypeFilter]);

  // Initial load with loader, background refreshes without
  const initialLoad = useRef(true);
  useEffect(() => {
    refresh(initialLoad.current);
    initialLoad.current = false;
  }, [refresh, refreshKey]);

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

  const handleCreate = async () => {
    if (!docTypeFilter) return;
    setCreating(true);
    setError(null);
    try {
      const doc = await createDocument(worldId, {
        doc_type: docTypeFilter,
        name: docTypeFilter !== "lore_fact" ? "New " + (DOC_TYPE_LABELS[docTypeFilter] || docTypeFilter) : undefined,
        content: "",
      });
      window.location.href = `/admin/worlds/${worldId}/documents/${doc.id}/edit`;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create document");
      setCreating(false);
    }
  };

  const createLabel = docTypeFilter ? `New ${DOC_TYPE_LABELS[docTypeFilter] || docTypeFilter}` : null;

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
        {createLabel && (
          <Button leftSection={<IconPlus size={16} />} onClick={handleCreate} loading={creating}>
            {createLabel}
          </Button>
        )}
      </Group>

      <input ref={fileInputRef} type="file" accept=".md,.txt" multiple style={{ display: "none" }} onChange={handleFileUpload} />

      {error && <Alert color="red" mb="md" withCloseButton onClose={() => setError(null)}>{error}</Alert>}

      {loading ? (
        <Group justify="center" py="xl"><Loader /></Group>
      ) : docs.length === 0 ? (
        <Text c="dimmed" ta="center" py="xl">No documents yet.</Text>
      ) : (() => {
        const isLoreTab = docTypeFilter === "lore_fact";
        const injected = isLoreTab ? [...docs].filter(d => d.is_injected).sort((a, b) => a.weight - b.weight) : [];
        const regular = isLoreTab ? docs.filter(d => !d.is_injected) : docs;

        const renderRow = (doc: DocumentItem) => {
          const editHref = `/admin/worlds/${worldId}/documents/${doc.id}/edit`;
          return (
            <Table.Tr
              key={doc.id}
              style={{ cursor: "pointer" }}
              onClick={() => { window.location.href = editHref; }}
            >
              <Table.Td>
                <Group gap={6} wrap="nowrap">
                  {doc.is_injected && <IconPin size={13} color="var(--mantine-color-orange-5)" style={{ flexShrink: 0 }} />}
                  <Text size="sm" fw={500} lineClamp={1}>{docDisplayName(doc)}</Text>
                </Group>
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
                    <Button variant="subtle" size="compact-sm" px={4} onClick={e => e.stopPropagation()}><IconDots size={16} /></Button>
                  </Menu.Target>
                  <Menu.Dropdown>
                    <Menu.Item leftSection={<IconEdit size={14} />} onClick={() => { window.location.href = editHref; }}>Edit</Menu.Item>
                    <Menu.Item leftSection={<IconDownload size={14} />} onClick={(e: React.MouseEvent) => { e.stopPropagation(); handleDownload(doc); }}>Download</Menu.Item>
                    <Menu.Item color="red" leftSection={<IconTrash size={14} />} onClick={(e: React.MouseEvent) => { e.stopPropagation(); handleDelete(doc); }}>Delete</Menu.Item>
                  </Menu.Dropdown>
                </Menu>
              </Table.Td>
            </Table.Tr>
          );
        };

        return (
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
              {injected.length > 0 && injected.map(renderRow)}
              {injected.length > 0 && regular.length > 0 && (
                <Table.Tr>
                  <Table.Td colSpan={3} py={4}>
                    <Text size="xs" c="dimmed" fs="italic">— search-only lore —</Text>
                  </Table.Td>
                </Table.Tr>
              )}
              {regular.map(renderRow)}
            </Table.Tbody>
          </Table>
        );
      })()}

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

const POLL_INTERVAL = 30_000; // refresh data every 30s

export function WorldViewPage() {
  const worldId = extractWorldId();
  const [world, setWorld] = useState<WorldDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string | null>(extractTab);
  const [refreshKey, setRefreshKey] = useState(0);

  const refreshWorld = useCallback(async (showLoader: boolean) => {
    if (!worldId) return;
    if (showLoader) setLoading(true);
    setError(null);
    try {
      setWorld(await getWorld(worldId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load world");
    } finally {
      if (showLoader) setLoading(false);
    }
  }, [worldId]);

  // Initial load
  useEffect(() => { refreshWorld(true); }, [refreshWorld]);

  // Periodic background refresh
  useEffect(() => {
    const id = setInterval(() => {
      refreshWorld(false);
      setRefreshKey(k => k + 1);
    }, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [refreshWorld]);

  // Re-fetch on tab change + update URL
  const handleTabChange = useCallback((tab: string | null) => {
    setActiveTab(tab);
    if (worldId && tab) {
      window.history.replaceState(null, "", tabUrl(worldId, tab));
    }
    refreshWorld(false);
    setRefreshKey(k => k + 1);
  }, [refreshWorld, worldId]);

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

      <Tabs value={activeTab} onChange={handleTabChange}>
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
          <DocsTab worldId={worldId} refreshKey={refreshKey} />
        </Tabs.Panel>

        <Tabs.Panel value="location">
          <DocsTab worldId={worldId} docTypeFilter="location" refreshKey={refreshKey} />
        </Tabs.Panel>

        <Tabs.Panel value="npc">
          <DocsTab worldId={worldId} docTypeFilter="npc" refreshKey={refreshKey} />
        </Tabs.Panel>

        <Tabs.Panel value="lore_fact">
          <DocsTab worldId={worldId} docTypeFilter="lore_fact" refreshKey={refreshKey} />
        </Tabs.Panel>

        <Tabs.Panel value="chats">
          <ChatsTab />
        </Tabs.Panel>
      </Tabs>
    </Container>
  );
}
