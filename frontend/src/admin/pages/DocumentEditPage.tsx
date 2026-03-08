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
  MultiSelect,
  Paper,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import {
  IconArrowLeft,
  IconPlus,
  IconTrash,
} from "@tabler/icons-react";
import type { DocumentItem } from "../../types/world";
import {
  createLink,
  deleteLink,
  getDocument,
  listDocuments,
  updateDocument,
} from "../../api/worlds";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractIds(): { worldId: string; docId: string } | null {
  const m = window.location.pathname.match(/\/admin\/worlds\/(\d+)\/documents\/(\d+)\/edit/);
  return m ? { worldId: m[1], docId: m[2] } : null;
}

const DOC_TYPE_LABELS: Record<string, string> = {
  location: "Location",
  npc: "NPC",
  lore_fact: "Lore Fact",
};

// ---------------------------------------------------------------------------
// Add link modal (for NPCs)
// ---------------------------------------------------------------------------

interface AddLinkModalProps {
  opened: boolean;
  worldId: string;
  npcId: string;
  existingLocationIds: Set<string>;
  onClose: () => void;
  onSaved: () => void;
}

function AddNpcLinkModal({ opened, worldId, npcId, existingLocationIds, onClose, onSaved }: AddLinkModalProps) {
  const [locations, setLocations] = useState<{ value: string; label: string }[]>([]);
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null);
  const [linkType, setLinkType] = useState("present");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!opened) return;
    setSelectedLocation(null);
    setLinkType("present");
    setError(null);
    // Load available locations
    listDocuments(worldId, "location").then(docs => {
      setLocations(
        docs
          .filter(d => !existingLocationIds.has(d.id))
          .map(d => ({ value: d.id, label: d.name || "(untitled)" }))
      );
    });
  }, [opened, worldId, existingLocationIds]);

  const handleSubmit = async () => {
    if (!selectedLocation) { setError("Select a location"); return; }
    setLoading(true);
    setError(null);
    try {
      await createLink(worldId, { npc_id: npcId, location_id: selectedLocation, link_type: linkType });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create link");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Add Location Link">
      <Stack>
        {error && <Alert color="red">{error}</Alert>}
        <Select label="Location" data={locations} value={selectedLocation} onChange={setSelectedLocation} searchable />
        <Select
          label="Link Type"
          data={[
            { value: "present", label: "Present (NPC is here)" },
            { value: "excluded", label: "Excluded (NPC cannot go here)" },
          ]}
          value={linkType}
          onChange={v => setLinkType(v || "present")}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} loading={loading}>Add Link</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Add link modal (for Locations — link NPCs)
// ---------------------------------------------------------------------------

interface AddLocationLinkModalProps {
  opened: boolean;
  worldId: string;
  locationId: string;
  existingNpcIds: Set<string>;
  onClose: () => void;
  onSaved: () => void;
}

function AddLocationLinkModal({ opened, worldId, locationId, existingNpcIds, onClose, onSaved }: AddLocationLinkModalProps) {
  const [npcOptions, setNpcOptions] = useState<{ value: string; label: string }[]>([]);
  const [selectedNpc, setSelectedNpc] = useState<string | null>(null);
  const [linkType, setLinkType] = useState("present");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!opened) return;
    setSelectedNpc(null);
    setLinkType("present");
    setError(null);
    listDocuments(worldId, "npc").then(docs => {
      setNpcOptions(
        docs
          .filter(d => !existingNpcIds.has(d.id))
          .map(d => ({ value: d.id, label: d.name || "(untitled)" }))
      );
    });
  }, [opened, worldId, existingNpcIds]);

  const handleSubmit = async () => {
    if (!selectedNpc) { setError("Select an NPC"); return; }
    setLoading(true);
    setError(null);
    try {
      await createLink(worldId, { npc_id: selectedNpc, location_id: locationId, link_type: linkType });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create link");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Link NPC">
      <Stack>
        {error && <Alert color="red">{error}</Alert>}
        <Select label="NPC" data={npcOptions} value={selectedNpc} onChange={setSelectedNpc} searchable />
        <Select
          label="Link Type"
          data={[
            { value: "present", label: "Present (NPC is here)" },
            { value: "excluded", label: "Excluded (NPC cannot come here)" },
          ]}
          value={linkType}
          onChange={v => setLinkType(v || "present")}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} loading={loading}>Add Link</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function DocumentEditPage() {
  const ids = extractIds();
  const worldId = ids?.worldId || "";
  const docId = ids?.docId || "";

  const [doc, setDoc] = useState<DocumentItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [embeddingWarning, setEmbeddingWarning] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [exits, setExits] = useState<string[]>([]);

  // Location options for exits
  const [locationOptions, setLocationOptions] = useState<{ value: string; label: string }[]>([]);

  // Link management
  const [addLinkOpen, setAddLinkOpen] = useState(false);

  const loadDoc = useCallback(async () => {
    if (!worldId || !docId) return;
    setLoading(true);
    setError(null);
    try {
      const document = await getDocument(worldId, docId);
      setDoc(document);
      setName(document.name || "");
      setContent(document.content);
      setExits(document.exits || []);

      // Load location options for exits dropdown
      if (document.doc_type === "location") {
        const locs = await listDocuments(worldId, "location");
        setLocationOptions(
          locs
            .filter(l => l.id !== docId)
            .map(l => ({ value: l.id, label: l.name || "(untitled)" }))
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load document");
    } finally {
      setLoading(false);
    }
  }, [worldId, docId]);

  useEffect(() => {
    loadDoc();
  }, [loadDoc]);

  const handleSave = async () => {
    if (!worldId || !docId || !doc) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    setEmbeddingWarning(null);
    try {
      const result = await updateDocument(worldId, docId, {
        name: doc.doc_type !== "lore_fact" ? name : undefined,
        content,
        exits: doc.doc_type === "location" ? exits : undefined,
      });
      if (result.embedding_warning) {
        setEmbeddingWarning(result.embedding_warning);
      }
      setSuccess("Document saved");
      setTimeout(() => setSuccess(null), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save document");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteLink = async (linkId: string) => {
    if (!worldId) return;
    try {
      await deleteLink(worldId, linkId);
      await loadDoc();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete link");
    }
  };

  if (!ids) return <Container py="md"><Alert color="red">Invalid URL</Alert></Container>;
  if (loading) return <Container py="md"><Group justify="center" py="xl"><Loader /></Group></Container>;
  if (!doc) return <Container py="md"><Alert color="red">Document not found</Alert></Container>;

  const existingLocationIds = new Set((doc.links || []).map(l => l.location_id));
  const existingNpcIds = new Set((doc.linked_npcs || []).map(n => n.npc_id));

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Group>
          <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => { window.location.href = `/admin/worlds/${worldId}/documents`; }}>
            Back
          </Button>
          <Title order={3}>{DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}: {name || "(untitled)"}</Title>
          <Badge>{DOC_TYPE_LABELS[doc.doc_type]}</Badge>
        </Group>
        <Button onClick={handleSave} loading={saving}>Save</Button>
      </Group>

      {error && <Alert color="red" mb="md" withCloseButton onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert color="green" mb="md" withCloseButton onClose={() => setSuccess(null)}>{success}</Alert>}
      {embeddingWarning && <Alert color="yellow" mb="md" withCloseButton onClose={() => setEmbeddingWarning(null)}>{embeddingWarning}</Alert>}

      <Paper p="md" mb="md" withBorder>
        <Stack>
          {doc.doc_type !== "lore_fact" && (
            <TextInput label="Name" value={name} onChange={e => setName(e.currentTarget.value)} />
          )}
          <Textarea
            label="Content"
            value={content}
            onChange={e => setContent(e.currentTarget.value)}
            minRows={12}
            autosize
            maxRows={30}
            styles={{ input: { fontFamily: "monospace" } }}
          />
          {doc.doc_type === "location" && (
            <MultiSelect
              label="Exits (connected locations)"
              data={locationOptions}
              value={exits}
              onChange={setExits}
              searchable
              clearable
            />
          )}
        </Stack>
      </Paper>

      {/* NPC links section (for NPC documents) */}
      {doc.doc_type === "npc" && (
        <Paper p="md" mb="md" withBorder>
          <Group justify="space-between" mb="sm">
            <Title order={5}>Location Links</Title>
            <Button size="compact-sm" leftSection={<IconPlus size={14} />} onClick={() => setAddLinkOpen(true)}>
              Add Link
            </Button>
          </Group>
          {(!doc.links || doc.links.length === 0) ? (
            <Text c="dimmed" size="sm">No location links. This NPC roams freely.</Text>
          ) : (
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Location</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th w={50} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {doc.links.map(link => (
                  <Table.Tr key={link.link_id}>
                    <Table.Td>{link.location_name}</Table.Td>
                    <Table.Td>
                      <Badge size="sm" color={link.link_type === "present" ? "green" : "red"}>
                        {link.link_type}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <ActionIcon variant="subtle" size="sm" color="red" onClick={() => handleDeleteLink(link.link_id)}>
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
          <AddNpcLinkModal
            opened={addLinkOpen}
            worldId={worldId}
            npcId={docId}
            existingLocationIds={existingLocationIds}
            onClose={() => setAddLinkOpen(false)}
            onSaved={loadDoc}
          />
        </Paper>
      )}

      {/* Linked NPCs section (for Location documents) */}
      {doc.doc_type === "location" && (
        <Paper p="md" mb="md" withBorder>
          <Group justify="space-between" mb="sm">
            <Title order={5}>Linked NPCs</Title>
            <Button size="compact-sm" leftSection={<IconPlus size={14} />} onClick={() => setAddLinkOpen(true)}>
              Link NPC
            </Button>
          </Group>
          {(!doc.linked_npcs || doc.linked_npcs.length === 0) ? (
            <Text c="dimmed" size="sm">No NPCs linked to this location.</Text>
          ) : (
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>NPC</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th w={50} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {doc.linked_npcs.map(link => (
                  <Table.Tr key={link.link_id}>
                    <Table.Td>{link.npc_name}</Table.Td>
                    <Table.Td>
                      <Badge size="sm" color={link.link_type === "present" ? "green" : "red"}>
                        {link.link_type}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <ActionIcon variant="subtle" size="sm" color="red" onClick={() => handleDeleteLink(link.link_id)}>
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
          <AddLocationLinkModal
            opened={addLinkOpen}
            worldId={worldId}
            locationId={docId}
            existingNpcIds={existingNpcIds}
            onClose={() => setAddLinkOpen(false)}
            onSaved={loadDoc}
          />
        </Paper>
      )}
    </Container>
  );
}
