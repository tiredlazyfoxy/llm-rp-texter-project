import { useEffect, useRef, useState } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { IconArrowLeft } from "@tabler/icons-react";
import { LlmChatPanel } from "../components/llm/LlmChatPanel";
import { PlaceholderPanel } from "../components/placeholders/PlaceholderPanel";
import {
  PlaceholderTextarea,
  type PlaceholderTextareaController,
} from "../components/placeholders/PlaceholderTextarea";
import { RUNTIME_PLACEHOLDERS } from "../components/placeholders/runtimePlaceholders";
import {
  WorldFieldEditPageState,
  WorldFieldName,
  loadField,
  saveField,
} from "./worldFieldEditPageState";

interface WorldFieldEditPageProps {
  worldId: string;
  fieldName: WorldFieldName;
}

export const WorldFieldEditPage = observer(function WorldFieldEditPage({
  worldId,
  fieldName,
}: WorldFieldEditPageProps) {
  const [state] = useState(() => new WorldFieldEditPageState(worldId, fieldName));
  const navigate = useNavigate();
  const controllerRef = useRef<PlaceholderTextareaController | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    void loadField(state, ctrl.signal);
    return () => ctrl.abort();
  }, []);

  const handleApply = async () => {
    if (!state.canSubmit) return;
    const ctrl = new AbortController();
    await saveField(state, ctrl.signal);
    if (state.saveSuccess) {
      setTimeout(() => {
        if (state.saveSuccess) state.saveSuccess = null;
      }, 3000);
    }
  };

  const handleInsertPlaceholder = (name: string) => {
    const text = "{" + name + "}";
    if (controllerRef.current) {
      controllerRef.current.insertAtCursor(text);
    } else {
      state.draft = state.draft + text;
    }
  };

  if (state.worldStatus === "loading" || state.worldStatus === "idle") {
    return (
      <Container pt="xl">
        <Loader />
      </Container>
    );
  }

  if (state.worldStatus === "error") {
    return (
      <Container pt="xl">
        <Alert color="red">{state.worldError}</Alert>
      </Container>
    );
  }

  return (
    <Container size="lg" py="md">
      {/* Top bar */}
      <Group justify="space-between" mb="md">
        <Group>
          <Button
            variant="subtle"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => navigate(`/worlds/${worldId}/edit`)}
          >
            Back
          </Button>
          <Title order={4}>
            <Text span c="dimmed" size="sm" mr={6}>World field</Text>
            <Badge variant="light">{state.fieldLabel}</Badge>
          </Title>
        </Group>
        <Group>
          {state.isDirty && (
            <Button
              onClick={handleApply}
              disabled={!state.canSubmit}
              loading={state.saveStatus === "loading"}
            >
              Apply
            </Button>
          )}
        </Group>
      </Group>

      {state.saveError && <Alert color="red" mb="md">{state.saveError}</Alert>}
      {state.saveSuccess && <Alert color="green" mb="md">{state.saveSuccess}</Alert>}

      <Stack gap="md">
        {/* Field textarea */}
        <div
          style={{
            height: "60vh",
            overflow: "auto",
            resize: "vertical",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {state.fieldName === "initial_message" ? (
            <PlaceholderTextarea
              value={state.draft}
              onChange={(v) => { state.draft = v; }}
              placeholders={RUNTIME_PLACEHOLDERS}
              controllerRef={controllerRef}
              textareaProps={{
                autosize: false,
                styles: {
                  root: { height: "100%", display: "flex", flexDirection: "column" },
                  wrapper: { flex: 1, display: "flex" },
                  input: { flex: 1, height: "100%", fontFamily: "monospace", resize: "none" },
                },
              }}
            />
          ) : (
            <Textarea
              value={state.draft}
              onChange={(e) => { state.draft = e.currentTarget.value; }}
              autosize
              minRows={4}
              styles={{ input: { fontFamily: "monospace" } }}
            />
          )}
        </div>

        {/* Placeholder reference panel — initial_message only */}
        {state.fieldName === "initial_message" && (
          <PlaceholderPanel
            placeholders={RUNTIME_PLACEHOLDERS}
            content={state.draft}
            onInsert={handleInsertPlaceholder}
          />
        )}

        {/* LLM chat panel */}
        <LlmChatPanel
          currentContent={state.draft}
          worldId={worldId}
          fieldType={fieldName}
          onApply={(text) => { state.draft = text; }}
          onAppend={(text) => { state.draft = state.draft + "\n\n" + text; }}
        />
      </Stack>
    </Container>
  );
});
