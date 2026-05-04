import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  MultiSelect,
  NumberInput,
  Paper,
  Stack,
  Switch,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { IconArrowLeft } from "@tabler/icons-react";
import type { DocumentItem } from "../../types/world";
import { LlmChatPanel } from "../components/llm/LlmChatPanel";
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
  const [originalContent, setOriginalContent] = useState("");
  const [exits, setExits] = useState<string[]>([]);
  const [isInjected, setIsInjected] = useState(false);
  const [weight, setWeight] = useState(0);

  // Location options for exits
  const [locationOptions, setLocationOptions] = useState<{ value: string; label: string }[]>([]);

  // Link state: allowed (present) and prohibited (excluded) IDs
  const [allowedIds, setAllowedIds] = useState<string[]>([]);
  const [prohibitedIds, setProhibitedIds] = useState<string[]>([]);
  // All options for the "other" type (locations for NPC, NPCs for location)
  const [linkOptions, setLinkOptions] = useState<{ value: string; label: string }[]>([]);

  const loadDoc = useCallback(async () => {
    if (!worldId || !docId) return;
    setLoading(true);
    setError(null);
    try {
      const document = await getDocument(worldId, docId);
      setDoc(document);
      setName(document.name || "");
      setContent(document.content);
      setOriginalContent(document.content);
      setExits(document.exits || []);
      setIsInjected(document.is_injected);
      setWeight(document.weight);

      if (document.doc_type === "npc") {
        // Load all locations for link multiselects
        const locs = await listDocuments(worldId, "location");
        setLinkOptions(locs.map(l => ({ value: l.id, label: l.name || "(untitled)" })));
        const links = document.links || [];
        setAllowedIds(links.filter(l => l.link_type === "present").map(l => l.location_id));
        setProhibitedIds(links.filter(l => l.link_type === "excluded").map(l => l.location_id));
      } else if (document.doc_type === "location") {
        // Load all locations for exits + all NPCs for link multiselects
        const [locs, npcs] = await Promise.all([
          listDocuments(worldId, "location"),
          listDocuments(worldId, "npc"),
        ]);
        setLocationOptions(
          locs.filter(l => l.id !== docId).map(l => ({ value: l.id, label: l.name || "(untitled)" }))
        );
        setLinkOptions(npcs.map(n => ({ value: n.id, label: n.name || "(untitled)" })));
        const links = document.linked_npcs || [];
        setAllowedIds(links.filter(l => l.link_type === "present").map(l => l.npc_id));
        setProhibitedIds(links.filter(l => l.link_type === "excluded").map(l => l.npc_id));
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

  // Sync link changes with the API (diff current vs new, create/delete as needed)
  const syncLinks = useCallback(async (
    linkType: string,
    oldIds: string[],
    newIds: string[],
  ) => {
    if (!doc) return;
    const oldSet = new Set(oldIds);
    const newSet = new Set(newIds);
    const toCreate = newIds.filter(id => !oldSet.has(id));
    const toDelete = oldIds.filter(id => !newSet.has(id));

    // Find link_ids for items to delete
    for (const id of toDelete) {
      let linkId: string | undefined;
      if (doc.doc_type === "npc") {
        linkId = (doc.links || []).find(l => l.location_id === id && l.link_type === linkType)?.link_id;
      } else {
        linkId = (doc.linked_npcs || []).find(l => l.npc_id === id && l.link_type === linkType)?.link_id;
      }
      if (linkId) await deleteLink(worldId, linkId);
    }

    for (const id of toCreate) {
      if (doc.doc_type === "npc") {
        await createLink(worldId, { npc_id: docId, location_id: id, link_type: linkType });
      } else {
        await createLink(worldId, { npc_id: id, location_id: docId, link_type: linkType });
      }
    }
  }, [doc, worldId, docId]);

  // When allowed changes, remove any overlapping items from prohibited
  const handleAllowedChange = (newAllowed: string[]) => {
    setAllowedIds(newAllowed);
    const newSet = new Set(newAllowed);
    setProhibitedIds(prev => prev.filter(id => !newSet.has(id)));
  };

  const handleProhibitedChange = (newProhibited: string[]) => {
    setProhibitedIds(newProhibited);
    const newSet = new Set(newProhibited);
    setAllowedIds(prev => prev.filter(id => !newSet.has(id)));
  };

  const handleSave = async () => {
    if (!worldId || !docId || !doc) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    setEmbeddingWarning(null);
    try {
      // Save document fields
      const result = await updateDocument(worldId, docId, {
        name: doc.doc_type !== "lore_fact" ? name : undefined,
        content,
        exits: doc.doc_type === "location" ? exits : undefined,
        is_injected: doc.doc_type === "lore_fact" ? isInjected : undefined,
        weight: doc.doc_type === "lore_fact" ? weight : undefined,
      });
      if (result.embedding_warning) {
        setEmbeddingWarning(result.embedding_warning);
      }

      // Sync links if NPC or location
      if (doc.doc_type === "npc") {
        const currentAllowed = (doc.links || []).filter(l => l.link_type === "present").map(l => l.location_id);
        const currentProhibited = (doc.links || []).filter(l => l.link_type === "excluded").map(l => l.location_id);
        await syncLinks("present", currentAllowed, allowedIds);
        await syncLinks("excluded", currentProhibited, prohibitedIds);
      } else if (doc.doc_type === "location") {
        const currentAllowed = (doc.linked_npcs || []).filter(l => l.link_type === "present").map(l => l.npc_id);
        const currentProhibited = (doc.linked_npcs || []).filter(l => l.link_type === "excluded").map(l => l.npc_id);
        await syncLinks("present", currentAllowed, allowedIds);
        await syncLinks("excluded", currentProhibited, prohibitedIds);
      }

      // Reload to get fresh link data
      await loadDoc();
      setSuccess("Document saved");
      setTimeout(() => setSuccess(null), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save document");
    } finally {
      setSaving(false);
    }
  };

  if (!ids) return <Container py="md"><Alert color="red">Invalid URL</Alert></Container>;
  if (loading) return <Container py="md"><Group justify="center" py="xl"><Loader /></Group></Container>;
  if (!doc) return <Container py="md"><Alert color="red">Document not found</Alert></Container>;

  // Filter options: items in allowed can't appear in prohibited and vice versa
  const allowedSet = new Set(allowedIds);
  const prohibitedSet = new Set(prohibitedIds);
  const allowedOptions = linkOptions.filter(o => !prohibitedSet.has(o.value));
  const prohibitedOptions = linkOptions.filter(o => !allowedSet.has(o.value));

  const isContentDirty = content !== originalContent
    || (doc?.doc_type === "lore_fact" && (isInjected !== doc.is_injected || weight !== doc.weight));
  const linkLabel = doc.doc_type === "npc" ? "Locations" : "NPCs";

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Group>
          <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => {
            if (isContentDirty && !window.confirm("You have unsaved changes. Leave anyway?")) return;
            history.back();
          }}>
            Back
          </Button>
          {doc.doc_type !== "lore_fact" && (
            <Title order={3}>{DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}: {name || "(untitled)"}</Title>
          )}
          <Badge>{DOC_TYPE_LABELS[doc.doc_type]}</Badge>
        </Group>
        {isContentDirty && <Button onClick={handleSave} loading={saving}>Save</Button>}
      </Group>

      {error && <Alert color="red" mb="md" withCloseButton onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert color="green" mb="md" withCloseButton onClose={() => setSuccess(null)}>{success}</Alert>}
      {embeddingWarning && <Alert color="yellow" mb="md" withCloseButton onClose={() => setEmbeddingWarning(null)}>{embeddingWarning}</Alert>}

      {/* Lore fact metadata: inject toggle + weight */}
      {doc.doc_type === "lore_fact" && (
        <Paper p="md" mb="md" withBorder>
          <Stack gap="sm">
            <Switch
              label="Always inject into context"
              description="When enabled, this lore fact is always included in the system prompt (even with tools mode). Excluded from tool search results."
              checked={isInjected}
              onChange={e => setIsInjected(e.currentTarget.checked)}
            />
            {isInjected && (
              <NumberInput
                label="Injection order"
                description="Lower numbers appear first in the injected context."
                value={weight}
                onChange={v => setWeight(typeof v === "number" ? v : 0)}
                min={0}
                w={160}
              />
            )}
          </Stack>
        </Paper>
      )}

      {/* Metadata: name, exits, links */}
      {doc.doc_type !== "lore_fact" && (
        <Paper p="md" mb="md" withBorder>
          <Stack>
            <TextInput label="Name" value={name} onChange={e => setName(e.currentTarget.value)} />
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
            {(doc.doc_type === "npc" || doc.doc_type === "location") && (
              <>
                <Text fw={600} size="sm">{linkLabel}</Text>
                <MultiSelect
                  label={`Allowed ${linkLabel}`}
                  description={doc.doc_type === "npc" ? "Locations where this NPC can be found" : "NPCs that can appear at this location"}
                  data={allowedOptions}
                  value={allowedIds}
                  onChange={handleAllowedChange}
                  searchable
                  clearable
                />
                <MultiSelect
                  label={`Prohibited ${linkLabel}`}
                  description={doc.doc_type === "npc" ? "Locations where this NPC cannot go" : "NPCs that cannot appear at this location"}
                  data={prohibitedOptions}
                  value={prohibitedIds}
                  onChange={handleProhibitedChange}
                  searchable
                  clearable
                />
              </>
            )}
          </Stack>
        </Paper>
      )}

      {/* Content editor */}
      <Textarea
        label="Content"
        value={content}
        onChange={e => setContent(e.currentTarget.value)}
        minRows={12}
        autosize
        maxRows={30}
        mb="md"
        styles={{ input: { fontFamily: "monospace" } }}
      />

      {/* LLM Chat */}
      <LlmChatPanel
        currentContent={content}
        worldId={worldId}
        docId={docId}
        docType={doc.doc_type as "location" | "npc" | "lore_fact"}
        onApply={(text) => setContent(text)}
        onAppend={(text) => setContent((prev) => prev + "\n\n" + text)}
      />
    </Container>
  );
}
