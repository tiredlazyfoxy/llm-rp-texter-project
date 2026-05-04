import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  Container,
  Group,
  Loader,
  MultiSelect,
  NumberInput,
  Paper,
  Select,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import {
  IconArrowDown,
  IconArrowLeft,
  IconArrowUp,
  IconCopy,
  IconSparkles,
  IconTrash,
} from "@tabler/icons-react";
import { getCurrentUser } from "../../auth";
import {
  PipelineEditPageState,
  addStage,
  deleteCurrentPipeline,
  loadPipelineEdit,
  removeStage,
  reorderStages,
  savePipeline,
  seedChainStages,
  toggleStageExpanded,
  updateStage,
} from "./pipelineEditPageState";

// ---------------------------------------------------------------------------
// Page props
// ---------------------------------------------------------------------------

interface PipelineEditPageProps {
  pipelineId: string | null;
  cloneFromId: string | null;
}

export const PipelineEditPage = observer(function PipelineEditPage({
  pipelineId,
  cloneFromId,
}: PipelineEditPageProps) {
  const [state] = useState(() => new PipelineEditPageState(pipelineId, cloneFromId));
  const navigate = useNavigate();

  useEffect(() => {
    const ctrl = new AbortController();
    void loadPipelineEdit(state, ctrl.signal);
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isAdmin = getCurrentUser()?.role === "admin";

  const handleSave = async () => {
    if (!state.canSubmit) return;
    const ctrl = new AbortController();
    const newId = await savePipeline(state, ctrl.signal);
    if (newId !== null) {
      // Shadow → edit transition: navigate to the freshly created record.
      navigate(`/pipelines/${newId}`);
      return;
    }
    if (state.saveSuccess) {
      setTimeout(() => {
        if (state.saveSuccess) state.saveSuccess = null;
      }, 3000);
    }
  };

  const handleDelete = async () => {
    if (state.mode !== "edit" || !state.pipelineId) return;
    if (!window.confirm(`Delete pipeline "${state.draft.name}"?`)) return;
    const ctrl = new AbortController();
    const ok = await deleteCurrentPipeline(state, ctrl.signal);
    if (ok) navigate("/pipelines");
  };

  if (state.loadStatus === "loading" || state.loadStatus === "idle") {
    return (
      <Container py="md">
        <Group justify="center" py="xl"><Loader /></Group>
      </Container>
    );
  }
  if (state.loadStatus === "error") {
    return <Container py="md"><Alert color="red">{state.loadError}</Alert></Container>;
  }

  // ---- Tools select data (grouped by category) -----------------------------

  const opts = state.configOptions;
  const toolsData = opts
    ? Object.entries(
        opts.tools.reduce<Record<string, { value: string; label: string }[]>>((acc, t) => {
          (acc[t.category] ??= []).push({ value: t.name, label: t.name });
          return acc;
        }, {}),
      ).map(([group, items]) => ({ group, items }))
    : [];

  const stages = state.draft.pipeline_config.stages;

  // ---- Render --------------------------------------------------------------

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Group>
          <Button
            variant="subtle"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => navigate("/pipelines")}
          >
            Back
          </Button>
          <Title order={3}>
            {state.mode === "shadow"
              ? (state.draft.name || "New pipeline")
              : (state.pipeline?.name || "Edit Pipeline")}
          </Title>
        </Group>
        <Group>
          {state.mode === "edit" && state.pipelineId && (
            <Button
              variant="light"
              leftSection={<IconCopy size={16} />}
              onClick={() => navigate(`/pipelines/new?cloneFrom=${state.pipelineId}`)}
              disabled={state.saveStatus === "loading"}
            >
              Clone
            </Button>
          )}
          {isAdmin && state.mode === "edit" && (
            <Button
              variant="light"
              color="red"
              leftSection={<IconTrash size={16} />}
              onClick={handleDelete}
            >
              Delete
            </Button>
          )}
          <Button
            onClick={handleSave}
            disabled={!state.canSubmit}
            loading={state.saveStatus === "loading"}
          >
            Save
          </Button>
        </Group>
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

      {/* Basics */}
      <Paper p="md" mb="md" withBorder>
        <Stack>
          <Group grow>
            <TextInput
              label="Name"
              value={state.draft.name}
              onChange={(e) => {
                state.draft.name = e.currentTarget.value;
                if (state.serverErrors.name) delete state.serverErrors.name;
              }}
              error={state.errors.name}
              required
            />
            <Select
              label="Kind"
              data={[
                { value: "simple", label: "Simple" },
                { value: "chain", label: "Chain Pipeline" },
                { value: "agentic", label: "Agentic (coming soon)", disabled: true },
              ]}
              value={state.draft.kind}
              onChange={(v) => {
                const next = v || "simple";
                state.draft.kind = next;
                if (next === "chain") seedChainStages(state);
              }}
            />
          </Group>
          <Textarea
            label="Description"
            value={state.draft.description}
            onChange={(e) => { state.draft.description = e.currentTarget.value; }}
            minRows={2}
          />
        </Stack>
      </Paper>

      {/* Mode body */}
      <Paper p="md" mb="md" withBorder>
        <Stack>
          {state.draft.kind === "simple" && (
            <>
              <Textarea
                label="System Prompt Template"
                description="Use {PLACEHOLDER} tokens for runtime injection."
                value={state.draft.system_prompt}
                onChange={(e) => { state.draft.system_prompt = e.currentTarget.value; }}
                autosize
                minRows={8}
                styles={{ input: { fontFamily: "monospace" } }}
              />
              {opts && (
                <MultiSelect
                  label="Enabled Tools"
                  description="Tools available to the LLM in simple mode. Empty = all tools."
                  data={toolsData}
                  value={state.draft.simple_tools}
                  onChange={(v) => { state.draft.simple_tools = v; }}
                  searchable
                  clearable
                />
              )}
            </>
          )}

          {state.draft.kind === "chain" && (
            <Stack gap="xs">
              <Group justify="space-between">
                <Text fw={500} size="sm">Pipeline Stages</Text>
                <Select
                  size="xs"
                  placeholder="Add stage..."
                  data={[
                    { value: "tool", label: "Tool" },
                    {
                      value: "writer",
                      label: "Writer",
                      disabled: stages.some(
                        (s) => s.step_type === "writer" || s.step_type === "writing",
                      ),
                    },
                  ]}
                  value={null}
                  onChange={(v) => {
                    if (!v) return;
                    addStage(state, v);
                  }}
                  clearable
                  w={160}
                />
              </Group>

              {/* Validation warnings */}
              {stages.length > 0 && (() => {
                const warnings: string[] = [];
                const last = stages[stages.length - 1];
                if (last.step_type !== "writer" && last.step_type !== "writing") {
                  warnings.push("Last stage should be a writer step");
                }
                if (!stages.some((s) => s.step_type === "writer" || s.step_type === "writing")) {
                  warnings.push("Pipeline needs at least one writer stage");
                }
                stages.forEach((s, i) => {
                  if ((s.step_type === "tool" || s.step_type === "planning") && s.tools.length === 0) {
                    warnings.push(`Stage ${i + 1}: no tools selected`);
                  }
                });
                return warnings.length > 0 ? (
                  <Alert color="yellow" variant="light">
                    {warnings.map((w, i) => <Text key={i} size="sm">{w}</Text>)}
                  </Alert>
                ) : null;
              })()}

              {stages.length === 0 ? (
                <Text c="dimmed" size="sm">No stages defined.</Text>
              ) : (
                stages.map((stage, idx) => {
                  const stageEnabled = stage.enabled !== false;
                  const expanded = state.expandedStages.has(idx);
                  return (
                    <Paper key={idx} p="xs" withBorder style={{ opacity: stageEnabled ? 1 : 0.55 }}>
                      <Stack gap={4}>
                        <Group justify="space-between" wrap="nowrap">
                          <Group gap="xs" wrap="nowrap">
                            <Checkbox
                              size="xs"
                              checked={stageEnabled}
                              onChange={(e) => updateStage(state, idx, { enabled: e.currentTarget.checked })}
                              title={stageEnabled ? "Disable stage" : "Enable stage"}
                            />
                            <Badge size="sm" variant="light" circle>{idx + 1}</Badge>
                            {!stageEnabled && <Badge size="sm" variant="filled" color="gray">Disabled</Badge>}
                            {(stage.step_type === "tool" || stage.step_type === "planning") ? (
                              <>
                                <TextInput
                                  size="xs"
                                  placeholder="Stage name"
                                  value={stage.name || ""}
                                  onChange={(e) => updateStage(state, idx, { name: e.currentTarget.value })}
                                  styles={stageEnabled ? undefined : { input: { textDecoration: "line-through" } }}
                                  w={150}
                                />
                                <NumberInput
                                  size="xs"
                                  placeholder="Max steps"
                                  title="Max agent steps"
                                  value={stage.max_agent_steps ?? 10}
                                  onChange={(v) =>
                                    updateStage(state, idx, {
                                      max_agent_steps: typeof v === "number" ? v : 10,
                                    })
                                  }
                                  min={1}
                                  max={50}
                                  w={80}
                                  ml="xs"
                                />
                              </>
                            ) : (
                              <Badge
                                size="sm"
                                variant="outline"
                                color="teal"
                                style={stageEnabled ? undefined : { textDecoration: "line-through" }}
                              >
                                {stage.step_type}
                              </Badge>
                            )}
                            <Select
                              size="xs"
                              placeholder="Session model"
                              title="Override model for this stage"
                              data={state.enabledModels.map((m) => ({ value: m.model_id, label: m.model_id }))}
                              value={stage.model_id ?? null}
                              onChange={(v) => updateStage(state, idx, { model_id: v })}
                              searchable
                              clearable
                              w={200}
                            />
                          </Group>
                          <Group gap={4} wrap="nowrap">
                            <ActionIcon
                              variant="subtle"
                              size="sm"
                              disabled={idx === 0}
                              onClick={() => reorderStages(state, idx, idx - 1)}
                            >
                              <IconArrowUp size={14} />
                            </ActionIcon>
                            <ActionIcon
                              variant="subtle"
                              size="sm"
                              disabled={idx === stages.length - 1}
                              onClick={() => reorderStages(state, idx, idx + 1)}
                            >
                              <IconArrowDown size={14} />
                            </ActionIcon>
                            <ActionIcon
                              variant="subtle"
                              size="sm"
                              title={state.mode === "shadow" ? "Save the pipeline first to edit stage prompts" : "Edit Prompt"}
                              disabled={state.mode === "shadow"}
                              onClick={() => {
                                if (state.mode === "shadow" || !state.pipelineId) return;
                                navigate(`/pipelines/${state.pipelineId}/stage/${idx}`);
                              }}
                            >
                              <IconSparkles size={14} />
                            </ActionIcon>
                            <ActionIcon
                              variant="subtle"
                              size="sm"
                              color="red"
                              onClick={() => removeStage(state, idx)}
                            >
                              <IconTrash size={14} />
                            </ActionIcon>
                          </Group>
                        </Group>
                        {opts && (
                          <MultiSelect
                            size="xs"
                            placeholder="Select tools..."
                            data={toolsData}
                            value={stage.tools || []}
                            onChange={(v) => updateStage(state, idx, { tools: v })}
                            searchable
                            clearable
                          />
                        )}
                        {stage.prompt ? (
                          <div
                            style={{
                              cursor: "pointer",
                              overflow: "hidden",
                              maxHeight: expanded ? undefined : "7.5em",
                              position: "relative",
                              fontSize: "var(--mantine-font-size-sm)",
                              color: "var(--mantine-color-dimmed)",
                            }}
                            onClick={() => toggleStageExpanded(state, idx)}
                          >
                            <ReactMarkdown>{stage.prompt}</ReactMarkdown>
                          </div>
                        ) : (
                          <Text size="sm" c="dimmed">(no prompt)</Text>
                        )}
                      </Stack>
                    </Paper>
                  );
                })
              )}
            </Stack>
          )}

          {state.draft.kind === "agentic" && (
            <Alert color="blue">Agent configuration coming soon</Alert>
          )}
        </Stack>
      </Paper>
    </Container>
  );
});
