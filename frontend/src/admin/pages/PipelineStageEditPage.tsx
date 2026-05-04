import { useEffect, useRef, useState } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Container,
  Group,
  Loader,
  Paper,
  Select,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconArrowLeft } from "@tabler/icons-react";
import { LlmChatPanel } from "../components/llm/LlmChatPanel";
import { PlaceholderPanel } from "../components/pipelines/PlaceholderPanel";
import {
  PlaceholderTextarea,
  type PlaceholderTextareaController,
} from "../components/pipelines/PlaceholderTextarea";
import {
  PipelineStageEditPageState,
  loadDefaultTemplate,
  loadStage,
  saveStage,
} from "./pipelineStageEditPageState";

interface PipelineStageEditPageProps {
  pipelineId: string;
  stageIndex: number;
}

export const PipelineStageEditPage = observer(function PipelineStageEditPage({
  pipelineId,
  stageIndex,
}: PipelineStageEditPageProps) {
  const [state] = useState(() => new PipelineStageEditPageState(pipelineId, stageIndex));
  const navigate = useNavigate();
  const controllerRef = useRef<PlaceholderTextareaController | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    void loadStage(state, ctrl.signal);
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleApply = async () => {
    if (!state.canSubmit) return;
    const ctrl = new AbortController();
    await saveStage(state, ctrl.signal);
    if (state.successMessage) {
      setTimeout(() => {
        if (state.successMessage) state.successMessage = null;
      }, 3000);
    }
  };

  const handleLoadDefault = () => {
    if (!state.configOptions) return;
    if (state.content && !window.confirm("Replace current content with default template?")) return;
    loadDefaultTemplate(state);
  };

  const handleInsertPlaceholder = (name: string) => {
    const text = `{${name}}`;
    if (controllerRef.current) {
      controllerRef.current.insertAtCursor(text);
    } else {
      state.content = state.content + text;
    }
  };

  if (state.loadStatus === "loading" || state.loadStatus === "idle") {
    return (
      <Container pt="xl">
        <Loader />
      </Container>
    );
  }
  if (state.loadStatus === "error") {
    return (
      <Container pt="xl">
        <Alert color="red">{state.loadError}</Alert>
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
            onClick={() => navigate(`/pipelines/${pipelineId}`)}
          >
            Back
          </Button>
          <Title order={4}>
            <Text span c="dimmed" size="sm" mr={6}>Pipeline stage {stageIndex + 1}</Text>
            {state.stageName && <Text span size="sm" fw={600} mr={6}>{state.stageName}</Text>}
            <Badge variant="light" color={(state.stepType === "tool" || state.stepType === "planning") ? "violet" : "teal"}>
              {state.stepType}
            </Badge>
          </Title>
        </Group>
        <Group>
          {state.configOptions && (
            <Button variant="default" size="compact-sm" onClick={handleLoadDefault}>
              Load Default Template
            </Button>
          )}
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
      {state.successMessage && <Alert color="green" mb="md">{state.successMessage}</Alert>}

      <Paper p="sm" withBorder mb="md">
        <Group gap="md" wrap="nowrap">
          <Checkbox
            label="Stage enabled"
            checked={state.stageEnabled}
            onChange={(e) => { state.stageEnabled = e.currentTarget.checked; }}
          />
          <Select
            label="Model override"
            description="Leave empty to use the session model"
            placeholder="Session model"
            data={state.enabledModels.map((m) => ({ value: m.model_id, label: m.model_id }))}
            value={state.stageModelId}
            onChange={(v) => { state.stageModelId = v; }}
            searchable
            clearable
            w={320}
          />
        </Group>
      </Paper>

      <Stack gap="md">
        {/* Prompt textarea */}
        <div style={{ height: "60vh", overflow: "auto", resize: "vertical" }}>
          <PlaceholderTextarea
            value={state.content}
            onChange={(v) => { state.content = v; }}
            placeholders={state.configOptions?.placeholders ?? []}
            controllerRef={controllerRef}
            textareaProps={{
              autosize: true,
              minRows: 12,
              styles: { input: { fontFamily: "monospace" } },
            }}
          />
        </div>

        {/* Placeholder reference panel */}
        {state.configOptions && (
          <PlaceholderPanel
            placeholders={state.configOptions.placeholders}
            content={state.content}
            onInsert={handleInsertPlaceholder}
          />
        )}

        {/* Enabled tools for this stage (read-only) */}
        {state.stageTools.length > 0 && (
          <Paper p="sm" withBorder>
            <Text size="sm" fw={500} mb="xs">Enabled Tools</Text>
            <Group gap="xs">
              {state.stageTools.map((t) => (
                <Badge key={t} size="sm" variant="light">{t}</Badge>
              ))}
            </Group>
          </Paper>
        )}

        {/* LLM chat panel — world-agnostic for pipeline prompts (no worldId passed) */}
        <LlmChatPanel
          currentContent={state.content}
          fieldType="pipeline_prompt"
          onApply={(text) => { state.content = text; }}
          onAppend={(text) => { state.content = state.content + "\n\n" + text; }}
        />
      </Stack>
    </Container>
  );
});
