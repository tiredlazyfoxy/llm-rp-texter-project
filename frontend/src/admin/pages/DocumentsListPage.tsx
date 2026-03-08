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
  Select,
  SegmentedControl,
  Stack,
  Table,
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
  IconTrash,
  IconUpload,
} from "@tabler/icons-react";
import type { DocumentItem } from "../../types/world";
import {
  createDocument,
  deleteDocument,
  downloadAllDocuments,
  downloadDocument,
  listDocuments,
  uploadDocuments,
} from "../../api/worlds";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractWorldId(): string | null {
  const m = window.location.pathname.match(/\/admin\/worlds\/(\d+)\/documents/);
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
// Main page
// ---------------------------------------------------------------------------

export function DocumentsListPage() {
  const worldId = extractWorldId();
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadType, setUploadType] = useState("location");

  const refresh = useCallback(async () => {
    if (!worldId) return;
    setLoading(true);
    setError(null);
    try {
      const docType = filter === "all" ? undefined : filter;
      setDocs(await listDocuments(worldId, docType));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [worldId, filter]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleDelete = async (doc: DocumentItem) => {
    if (!worldId) return;
    if (!window.confirm(`Delete "${docDisplayName(doc)}"?`)) return;
    try {
      await deleteDocument(worldId, doc.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete document");
    }
  };

  const handleDownload = async (doc: DocumentItem) => {
    if (!worldId) return;
    try {
      await downloadDocument(worldId, doc.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to download document");
    }
  };

  const handleDownloadAll = async () => {
    if (!worldId) return;
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
    if (!worldId) return;
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

  if (!worldId) return <Container py="md"><Alert color="red">Invalid world ID</Alert></Container>;

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Group>
          <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => { window.location.href = `/admin/worlds/${worldId}/edit`; }}>
            Back to World
          </Button>
          <Title order={3}>Documents</Title>
        </Group>
        <Group>
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
      </Group>

      <input ref={fileInputRef} type="file" accept=".md,.txt" multiple style={{ display: "none" }} onChange={handleFileUpload} />

      {error && <Alert color="red" mb="md" withCloseButton onClose={() => setError(null)}>{error}</Alert>}

      <SegmentedControl
        mb="md"
        value={filter}
        onChange={setFilter}
        data={[
          { value: "all", label: "All" },
          { value: "location", label: "Locations" },
          { value: "npc", label: "NPCs" },
          { value: "lore_fact", label: "Lore Facts" },
        ]}
      />

      {loading ? (
        <Group justify="center" py="xl"><Loader /></Group>
      ) : docs.length === 0 ? (
        <Text c="dimmed" ta="center" py="xl">No documents yet.</Text>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Type</Table.Th>
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
                <Table.Td>
                  <Badge size="sm" color={docTypeBadgeColor(doc.doc_type)}>
                    {DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
                  </Badge>
                </Table.Td>
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

      <CreateDocModal opened={createOpen} worldId={worldId} initialDocType={filter !== "all" ? filter : undefined} onClose={() => setCreateOpen(false)} onSaved={refresh} />
    </Container>
  );
}
