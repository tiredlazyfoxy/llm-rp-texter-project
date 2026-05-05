import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
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
import { formatDate } from "../../utils/formatDate";
import type { DocumentItem, WorldDetail } from "../../types/world";
import { getNewSnowflakeId } from "../../api/admin";
import {
  WorldViewPageState,
  WorldViewTab,
  VALID_TABS,
  loadWorld,
  refreshWorld,
  loadDocs,
  refreshDocs,
  deleteDocument,
  downloadDocument,
  downloadAllDocuments,
  uploadDocuments,
  reindexWorld,
} from "./worldViewPageState";

// ---------------------------------------------------------------------------
// Constants & helpers
// ---------------------------------------------------------------------------

const POLL_INTERVAL = 30_000;

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

function parseTab(raw: string | null): WorldViewTab {
  if (raw && (VALID_TABS as string[]).includes(raw)) return raw as WorldViewTab;
  return "info";
}

// ---------------------------------------------------------------------------
// Collapsible preformatted text block
// ---------------------------------------------------------------------------

const COLLAPSED_HEIGHT = 220;

function CollapsibleText({ text, mono = false }: { text: string; mono?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const [overflows, setOverflows] = useState(false);
  const innerRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (innerRef.current) {
      setOverflows(innerRef.current.scrollHeight > COLLAPSED_HEIGHT);
    }
  }, [text]);

  return (
    <div
      style={{ position: "relative", overflow: "hidden", maxHeight: expanded ? undefined : COLLAPSED_HEIGHT, background: "var(--mantine-color-default)", borderRadius: 4, cursor: overflows ? "pointer" : undefined }}
      onClick={() => overflows && setExpanded(e => !e)}
    >
      <div ref={innerRef} className="md-body" style={{ padding: "8px 10px", fontSize: "var(--mantine-font-size-sm)", fontFamily: mono ? "monospace" : undefined }}>
        <ReactMarkdown>{text}</ReactMarkdown>
      </div>
      {!expanded && overflows && (
        <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 48, background: "linear-gradient(transparent, var(--mantine-color-default))" }} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Info tab
// ---------------------------------------------------------------------------

const InfoTab = observer(function InfoTab({
  world,
  worldId,
}: {
  world: WorldDetail;
  worldId: string;
}) {
  const navigate = useNavigate();
  return (
    <Stack>
      <Group justify="flex-end">
        <Button
          leftSection={<IconEdit size={16} />}
          onClick={() => navigate(`/worlds/${worldId}/edit`)}
        >
          Edit World
        </Button>
      </Group>

      <Paper p="md" withBorder>
        <Stack gap="sm">
          <Group>
            <Text fw={600} w={120}>Status</Text>
            <Badge color={statusColor(world.status)}>{world.status}</Badge>
          </Group>
          <Stack gap={4}>
            <Text fw={600}>Description</Text>
            {world.description ? (
              <div className="md-body" style={{ background: "var(--mantine-color-default)", borderRadius: 4, padding: "8px 10px", fontSize: "var(--mantine-font-size-sm)" }}>
                <ReactMarkdown>{world.description}</ReactMarkdown>
              </div>
            ) : (
              <Text size="sm" c="dimmed">-</Text>
            )}
          </Stack>
          {world.initial_message && (
            <Stack gap={4}>
              <Text fw={600}>Initial Message</Text>
              <CollapsibleText text={world.initial_message} />
            </Stack>
          )}
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
});

// ---------------------------------------------------------------------------
// Documents tab
// ---------------------------------------------------------------------------

const DocsTab = observer(function DocsTab({ state }: { state: WorldViewPageState }) {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadType, setUploadType] = useState("location");

  const docTypeFilter = state.docTypeFilter;
  const loading = state.docsStatus === "loading" || state.docsStatus === "idle";

  const handleDelete = async (doc: DocumentItem) => {
    if (!window.confirm(`Delete "${docDisplayName(doc)}"?`)) return;
    const ctrl = new AbortController();
    await deleteDocument(state, doc, ctrl.signal);
  };

  const handleDownload = async (doc: DocumentItem) => {
    const ctrl = new AbortController();
    await downloadDocument(state, doc, ctrl.signal);
  };

  const handleDownloadAll = async () => {
    const ctrl = new AbortController();
    await downloadAllDocuments(state, ctrl.signal);
  };

  const handleUploadClick = (type: string) => {
    setUploadType(type);
    fileInputRef.current?.click();
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const ctrl = new AbortController();
    await uploadDocuments(state, Array.from(files), uploadType, ctrl.signal);
    e.target.value = "";
  };

  const handleReindex = async () => {
    const ctrl = new AbortController();
    const result = await reindexWorld(state, ctrl.signal);
    if (result && !result.warning) {
      window.alert(`Reindexed ${result.indexed_count} documents.`);
    }
  };

  const handleCreate = async () => {
    if (!docTypeFilter) return;
    state.createDocStatus = "loading";
    const ctrl = new AbortController();
    try {
      const newId = await getNewSnowflakeId(ctrl.signal);
      state.createDocStatus = "ready";
      navigate(`/worlds/${state.worldId}/documents/${newId}/edit?new=1&doc_type=${docTypeFilter}`);
    } catch (err) {
      if (ctrl.signal.aborted) return;
      state.createDocStatus = "error";
      state.docsError = err instanceof Error ? err.message : String(err);
    }
  };

  const createLabel = docTypeFilter ? `New ${DOC_TYPE_LABELS[docTypeFilter] || docTypeFilter}` : null;

  return (
    <Stack>
      <Group justify="flex-end">
        <Button
          variant="light"
          leftSection={<IconRefresh size={16} />}
          onClick={handleReindex}
          loading={state.reindexStatus === "loading"}
        >
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
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={handleCreate}
            loading={state.createDocStatus === "loading"}
          >
            {createLabel}
          </Button>
        )}
      </Group>

      <input ref={fileInputRef} type="file" accept=".md,.txt" multiple style={{ display: "none" }} onChange={handleFileUpload} />

      {state.docsError && (
        <Alert color="red" mb="md" withCloseButton onClose={() => { state.docsError = null; }}>
          {state.docsError}
        </Alert>
      )}
      {state.reindexError && (
        <Alert color="red" mb="md" withCloseButton onClose={() => { state.reindexError = null; }}>
          {state.reindexError}
        </Alert>
      )}

      {loading ? (
        <Group justify="center" py="xl"><Loader /></Group>
      ) : state.docs.length === 0 ? (
        <Text c="dimmed" ta="center" py="xl">No documents yet.</Text>
      ) : (() => {
        const isLoreTab = docTypeFilter === "lore_fact";
        const injected = isLoreTab ? [...state.docs].filter(d => d.is_injected).sort((a, b) => a.weight - b.weight) : [];
        const regular = isLoreTab ? state.docs.filter(d => !d.is_injected) : state.docs;

        const renderRow = (doc: DocumentItem) => {
          const editPath = `/worlds/${state.worldId}/documents/${doc.id}/edit`;
          return (
            <Table.Tr
              key={doc.id}
              style={{ cursor: "pointer" }}
              onClick={() => navigate(editPath)}
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
                    <Menu.Item leftSection={<IconEdit size={14} />} onClick={() => navigate(editPath)}>Edit</Menu.Item>
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
});

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

interface WorldViewPageProps {
  worldId: string;
}

export const WorldViewPage = observer(function WorldViewPage({ worldId }: WorldViewPageProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [state] = useState(() => new WorldViewPageState(worldId, parseTab(searchParams.get("tab"))));
  const navigate = useNavigate();

  useEffect(() => {
    const ctrl = new AbortController();
    loadWorld(state, ctrl.signal).then(() => {
      if (ctrl.signal.aborted) return;
      void loadDocs(state, ctrl.signal);
    });

    const pollId = setInterval(() => {
      void refreshWorld(state, ctrl.signal);
      void refreshDocs(state, ctrl.signal);
    }, POLL_INTERVAL);

    return () => {
      clearInterval(pollId);
      ctrl.abort();
    };
  }, []);

  const handleTabChange = (raw: string | null) => {
    const tab = parseTab(raw);
    state.tab = tab;
    setSearchParams(
      (prev) => {
        if (tab === "info") prev.delete("tab");
        else prev.set("tab", tab);
        return prev;
      },
      { replace: true },
    );
    const ctrl = new AbortController();
    void loadDocs(state, ctrl.signal);
  };

  if (state.worldStatus === "loading" || state.worldStatus === "idle") {
    return <Container py="md"><Group justify="center" py="xl"><Loader /></Group></Container>;
  }
  if (state.worldStatus === "error") {
    return <Container py="md"><Alert color="red">{state.worldError}</Alert></Container>;
  }
  const world = state.world;
  if (!world) return null;

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Group>
          <Button
            variant="subtle"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => navigate("/worlds")}
          >
            Back
          </Button>
          <Title order={3}>{world.name}</Title>
          <Badge color={statusColor(world.status)}>{world.status}</Badge>
        </Group>
      </Group>

      <Tabs value={state.tab} onChange={handleTabChange}>
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
          <DocsTab state={state} />
        </Tabs.Panel>

        <Tabs.Panel value="location">
          <DocsTab state={state} />
        </Tabs.Panel>

        <Tabs.Panel value="npc">
          <DocsTab state={state} />
        </Tabs.Panel>

        <Tabs.Panel value="lore_fact">
          <DocsTab state={state} />
        </Tabs.Panel>

        <Tabs.Panel value="chats">
          <ChatsTab />
        </Tabs.Panel>
      </Tabs>
    </Container>
  );
});
