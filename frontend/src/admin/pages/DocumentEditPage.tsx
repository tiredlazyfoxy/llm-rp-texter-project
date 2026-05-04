import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate } from "react-router-dom";
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
import { LlmChatPanel } from "../components/llm/LlmChatPanel";
import {
  DocumentEditPageState,
  loadDocument,
  saveDocument,
} from "./documentEditPageState";

const DOC_TYPE_LABELS: Record<string, string> = {
  location: "Location",
  npc: "NPC",
  lore_fact: "Lore Fact",
};

interface DocumentEditPageProps {
  worldId: string;
  docId: string;
}

export const DocumentEditPage = observer(function DocumentEditPage({
  worldId,
  docId,
}: DocumentEditPageProps) {
  const [state] = useState(() => new DocumentEditPageState(worldId, docId));
  const navigate = useNavigate();

  useEffect(() => {
    const ctrl = new AbortController();
    void loadDocument(state, ctrl.signal);
    return () => ctrl.abort();
  }, []);

  const handleSave = async () => {
    if (!state.canSubmit) return;
    const ctrl = new AbortController();
    await saveDocument(state, ctrl.signal);
    if (state.saveSuccess) {
      setTimeout(() => {
        if (state.saveSuccess) state.saveSuccess = null;
      }, 3000);
    }
  };

  const handleAllowedChange = (newAllowed: string[]) => {
    state.draft.allowedIds = newAllowed;
    const newSet = new Set(newAllowed);
    state.draft.prohibitedIds = state.draft.prohibitedIds.filter(id => !newSet.has(id));
  };

  const handleProhibitedChange = (newProhibited: string[]) => {
    state.draft.prohibitedIds = newProhibited;
    const newSet = new Set(newProhibited);
    state.draft.allowedIds = state.draft.allowedIds.filter(id => !newSet.has(id));
  };

  const handleBack = () => {
    if (state.isDirty && !window.confirm("You have unsaved changes. Leave anyway?")) return;
    navigate(`/worlds/${worldId}`);
  };

  if (state.loadStatus === "loading" || state.loadStatus === "idle") {
    return <Container py="md"><Group justify="center" py="xl"><Loader /></Group></Container>;
  }
  if (state.loadStatus === "error") {
    return <Container py="md"><Alert color="red">{state.loadError}</Alert></Container>;
  }
  const doc = state.doc;
  if (!doc) return <Container py="md"><Alert color="red">Document not found</Alert></Container>;

  // Filter options: items in allowed can't appear in prohibited and vice versa
  const allowedSet = new Set(state.draft.allowedIds);
  const prohibitedSet = new Set(state.draft.prohibitedIds);
  const allowedOptions = state.linkOptions.filter(o => !prohibitedSet.has(o.value));
  const prohibitedOptions = state.linkOptions.filter(o => !allowedSet.has(o.value));

  const linkLabel = doc.doc_type === "npc" ? "Locations" : "NPCs";

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Group>
          <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={handleBack}>
            Back
          </Button>
          {doc.doc_type !== "lore_fact" && (
            <Title order={3}>{DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}: {state.draft.name || "(untitled)"}</Title>
          )}
          <Badge>{DOC_TYPE_LABELS[doc.doc_type]}</Badge>
        </Group>
        {state.isDirty && (
          <Button
            onClick={handleSave}
            disabled={!state.canSubmit}
            loading={state.saveStatus === "loading"}
          >
            Save
          </Button>
        )}
      </Group>

      {state.saveError && (
        <Alert color="red" mb="md" withCloseButton onClose={() => { state.saveError = null; }}>
          {state.saveError}
        </Alert>
      )}
      {state.saveSuccess && (
        <Alert color="green" mb="md" withCloseButton onClose={() => { state.saveSuccess = null; }}>
          {state.saveSuccess}
        </Alert>
      )}
      {state.embeddingWarning && (
        <Alert color="yellow" mb="md" withCloseButton onClose={() => { state.embeddingWarning = null; }}>
          {state.embeddingWarning}
        </Alert>
      )}

      {/* Lore fact metadata */}
      {doc.doc_type === "lore_fact" && (
        <Paper p="md" mb="md" withBorder>
          <Stack gap="sm">
            <Switch
              label="Always inject into context"
              description="When enabled, this lore fact is always included in the system prompt (even with tools mode). Excluded from tool search results."
              checked={state.draft.isInjected}
              onChange={e => { state.draft.isInjected = e.currentTarget.checked; }}
            />
            {state.draft.isInjected && (
              <NumberInput
                label="Injection order"
                description="Lower numbers appear first in the injected context."
                value={state.draft.weight}
                onChange={v => { state.draft.weight = typeof v === "number" ? v : 0; }}
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
            <TextInput
              label="Name"
              value={state.draft.name}
              onChange={e => { state.draft.name = e.currentTarget.value; }}
            />
            {doc.doc_type === "location" && (
              <MultiSelect
                label="Exits (connected locations)"
                data={state.locationOptions}
                value={state.draft.exits}
                onChange={(v) => { state.draft.exits = v; }}
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
                  value={state.draft.allowedIds}
                  onChange={handleAllowedChange}
                  searchable
                  clearable
                />
                <MultiSelect
                  label={`Prohibited ${linkLabel}`}
                  description={doc.doc_type === "npc" ? "Locations where this NPC cannot go" : "NPCs that cannot appear at this location"}
                  data={prohibitedOptions}
                  value={state.draft.prohibitedIds}
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
        value={state.draft.content}
        onChange={e => { state.draft.content = e.currentTarget.value; }}
        minRows={12}
        autosize
        maxRows={30}
        mb="md"
        styles={{ input: { fontFamily: "monospace" } }}
      />

      {/* LLM Chat */}
      <LlmChatPanel
        currentContent={state.draft.content}
        worldId={worldId}
        docId={docId}
        docType={doc.doc_type as "location" | "npc" | "lore_fact"}
        onApply={(text) => { state.draft.content = text; }}
        onAppend={(text) => { state.draft.content = state.draft.content + "\n\n" + text; }}
      />
    </Container>
  );
});
