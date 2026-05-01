import { useCallback, useEffect, useRef, useState } from "react";
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
import { fetchEnabledModels } from "../../api/llmChat";
import type { EnabledModelInfo } from "../../types/llmServer";
import type {
  PipelineConfig,
  PipelineConfigOptions,
  PipelineItem,
  PipelineStage,
  UpdatePipelineRequest,
} from "../../types/pipeline";
import {
  createPipeline,
  deletePipeline,
  getPipeline,
  getPipelineConfigOptions,
  updatePipeline,
} from "../../api/pipelines";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type PageMode = "edit" | "shadow";
interface RouteInfo { mode: PageMode; pipelineId: string | null; cloneFromId: string | null; }

function parseRoute(): RouteInfo {
  const path = window.location.pathname;
  if (path === "/admin/pipelines/new") {
    const cloneFrom = new URLSearchParams(window.location.search).get("cloneFrom");
    return { mode: "shadow", pipelineId: null, cloneFromId: cloneFrom };
  }
  const m = path.match(/\/admin\/pipelines\/(\d+)$/);
  return { mode: "edit", pipelineId: m ? m[1] : null, cloneFromId: null };
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function PipelineEditPage() {
  const route = parseRoute();
  const { mode, pipelineId, cloneFromId } = route;
  const shadowAgentConfigRef = useRef<string>("{}");
  const [pipeline, setPipeline] = useState<PipelineItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState("simple");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [simpleTools, setSimpleTools] = useState<string[]>([]);
  const [pipelineConfig, setPipelineConfig] = useState<PipelineConfig>({ stages: [] });

  // Static config + models
  const [configOptions, setConfigOptions] = useState<PipelineConfigOptions | null>(null);
  const [enabledModels, setEnabledModels] = useState<EnabledModelInfo[]>([]);
  const [expandedStages, setExpandedStages] = useState<Set<number>>(new Set());

  const isAdmin = getCurrentUser()?.role === "admin";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (mode === "shadow") {
        if (!cloneFromId) {
          setError("Missing cloneFrom parameter");
          return;
        }
        const src = await getPipeline(cloneFromId);
        setName(`${src.name} (clone)`);
        setDescription(src.description);
        setKind(src.kind);
        setSystemPrompt(src.system_prompt);
        try { setSimpleTools(JSON.parse(src.simple_tools || "[]")); } catch { setSimpleTools([]); }
        try {
          const parsed = JSON.parse(src.pipeline_config || "{}");
          setPipelineConfig({ stages: parsed.stages || [] });
        } catch {
          setPipelineConfig({ stages: [] });
        }
        shadowAgentConfigRef.current = src.agent_config ?? "{}";
        return;
      }
      if (!pipelineId) return;
      const p = await getPipeline(pipelineId);
      setPipeline(p);
      setName(p.name);
      setDescription(p.description);
      setKind(p.kind);
      setSystemPrompt(p.system_prompt);
      try { setSimpleTools(JSON.parse(p.simple_tools || "[]")); } catch { setSimpleTools([]); }
      try {
        const parsed = JSON.parse(p.pipeline_config || "{}");
        setPipelineConfig({ stages: parsed.stages || [] });
      } catch {
        setPipelineConfig({ stages: [] });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load pipeline");
    } finally {
      setLoading(false);
    }
  }, [mode, pipelineId, cloneFromId]);

  useEffect(() => {
    void load();
    getPipelineConfigOptions().then(setConfigOptions).catch(() => {});
    fetchEnabledModels().then(setEnabledModels).catch(() => {});
  }, [load]);

  const handleSave = async () => {
    if (!name.trim()) { setError("Name is required"); return; }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      if (mode === "shadow") {
        const created = await createPipeline({
          name,
          description,
          kind,
          system_prompt: systemPrompt,
          simple_tools: JSON.stringify(simpleTools),
          pipeline_config: JSON.stringify(pipelineConfig),
          agent_config: shadowAgentConfigRef.current,
        });
        window.location.href = `/admin/pipelines/${created.id}`;
        return;
      }
      if (!pipelineId) return;
      const req: UpdatePipelineRequest = {
        name,
        description,
        kind,
        system_prompt: systemPrompt,
        simple_tools: JSON.stringify(simpleTools),
        pipeline_config: JSON.stringify(pipelineConfig),
      };
      const updated = await updatePipeline(pipelineId, req);
      setPipeline(updated);
      setSuccess("Pipeline saved");
      setTimeout(() => setSuccess(null), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save pipeline");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!pipelineId) return;
    if (!window.confirm(`Delete pipeline "${name}"?`)) return;
    try {
      await deletePipeline(pipelineId);
      window.location.href = "/admin/pipelines";
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (/referenced/i.test(msg)) {
        setError("This pipeline is referenced by one or more worlds — re-point them first.");
      } else {
        setError(msg);
      }
    }
  };

  if (mode === "edit" && !pipelineId) {
    return <Container py="md"><Alert color="red">Invalid pipeline ID</Alert></Container>;
  }
  if (mode === "shadow" && !cloneFromId) {
    return <Container py="md"><Alert color="red">Missing cloneFrom parameter</Alert></Container>;
  }

  if (loading) {
    return <Container py="md"><Group justify="center" py="xl"><Loader /></Group></Container>;
  }

  // ---- Tools select data (grouped by category) -----------------------------

  const toolsData = configOptions
    ? Object.entries(
        configOptions.tools.reduce<Record<string, { value: string; label: string }[]>>((acc, t) => {
          (acc[t.category] ??= []).push({ value: t.name, label: t.name });
          return acc;
        }, {}),
      ).map(([group, items]) => ({ group, items }))
    : [];

  // ---- Render --------------------------------------------------------------

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Group>
          <Button
            variant="subtle"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => { window.location.href = "/admin/pipelines"; }}
          >
            Back
          </Button>
          <Title order={3}>
            {mode === "shadow" ? (name || "New pipeline (clone)") : (pipeline?.name || "Edit Pipeline")}
          </Title>
        </Group>
        <Group>
          {mode === "edit" && (
            <Button
              variant="light"
              leftSection={<IconCopy size={16} />}
              onClick={() => { window.location.href = `/admin/pipelines/new?cloneFrom=${pipelineId}`; }}
              disabled={loading || saving}
            >
              Clone
            </Button>
          )}
          {isAdmin && mode === "edit" && (
            <Button
              variant="light"
              color="red"
              leftSection={<IconTrash size={16} />}
              onClick={handleDelete}
            >
              Delete
            </Button>
          )}
          <Button onClick={handleSave} loading={saving}>Save</Button>
        </Group>
      </Group>

      {error && <Alert color="red" mb="md" withCloseButton onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert color="green" mb="md" withCloseButton onClose={() => setSuccess(null)}>{success}</Alert>}

      {/* Basics */}
      <Paper p="md" mb="md" withBorder>
        <Stack>
          <Group grow>
            <TextInput
              label="Name"
              value={name}
              onChange={e => setName(e.currentTarget.value)}
              required
            />
            <Select
              label="Kind"
              data={[
                { value: "simple", label: "Simple" },
                { value: "chain", label: "Chain Pipeline" },
                { value: "agentic", label: "Agentic (coming soon)", disabled: true },
              ]}
              value={kind}
              onChange={v => {
                const next = v || "simple";
                setKind(next);
                if (next === "chain" && pipelineConfig.stages.length === 0) {
                  setPipelineConfig({
                    stages: [
                      { step_type: "tool", name: "", prompt: "", max_agent_steps: 10, tools: [], enabled: true, model_id: null },
                      { step_type: "writer", name: "", prompt: "", max_agent_steps: null, tools: [], enabled: true, model_id: null },
                    ],
                  });
                }
              }}
            />
          </Group>
          <Textarea
            label="Description"
            value={description}
            onChange={e => setDescription(e.currentTarget.value)}
            minRows={2}
          />
        </Stack>
      </Paper>

      {/* Mode body */}
      <Paper p="md" mb="md" withBorder>
        <Stack>
          {kind === "simple" && (
            <>
              <Textarea
                label="System Prompt Template"
                description="Use {PLACEHOLDER} tokens for runtime injection."
                value={systemPrompt}
                onChange={e => setSystemPrompt(e.currentTarget.value)}
                autosize
                minRows={8}
                styles={{ input: { fontFamily: "monospace" } }}
              />
              {configOptions && (
                <MultiSelect
                  label="Enabled Tools"
                  description="Tools available to the LLM in simple mode. Empty = all tools."
                  data={toolsData}
                  value={simpleTools}
                  onChange={setSimpleTools}
                  searchable
                  clearable
                />
              )}
            </>
          )}

          {kind === "chain" && (
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
                      disabled: pipelineConfig.stages.some(s => s.step_type === "writer" || s.step_type === "writing"),
                    },
                  ]}
                  value={null}
                  onChange={v => {
                    if (!v) return;
                    const newStage: PipelineStage = {
                      step_type: v,
                      name: "",
                      prompt: "",
                      max_agent_steps: v === "tool" ? 10 : null,
                      tools: [],
                      enabled: true,
                      model_id: null,
                    };
                    if (v === "tool") {
                      const writerIdx = pipelineConfig.stages.findIndex(
                        s => s.step_type === "writer" || s.step_type === "writing",
                      );
                      if (writerIdx !== -1) {
                        setPipelineConfig(prev => {
                          const stages = [...prev.stages];
                          stages.splice(writerIdx, 0, newStage);
                          return { stages };
                        });
                        return;
                      }
                    }
                    setPipelineConfig(prev => ({ stages: [...prev.stages, newStage] }));
                  }}
                  clearable
                  w={160}
                />
              </Group>

              {/* Validation warnings */}
              {pipelineConfig.stages.length > 0 && (() => {
                const warnings: string[] = [];
                const last = pipelineConfig.stages[pipelineConfig.stages.length - 1];
                if (last.step_type !== "writer" && last.step_type !== "writing") {
                  warnings.push("Last stage should be a writer step");
                }
                if (!pipelineConfig.stages.some(s => s.step_type === "writer" || s.step_type === "writing")) {
                  warnings.push("Pipeline needs at least one writer stage");
                }
                pipelineConfig.stages.forEach((s, i) => {
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

              {pipelineConfig.stages.length === 0 ? (
                <Text c="dimmed" size="sm">No stages defined.</Text>
              ) : (
                pipelineConfig.stages.map((stage, idx) => {
                  const stageEnabled = stage.enabled !== false;
                  return (
                    <Paper key={idx} p="xs" withBorder style={{ opacity: stageEnabled ? 1 : 0.55 }}>
                      <Stack gap={4}>
                        <Group justify="space-between" wrap="nowrap">
                          <Group gap="xs" wrap="nowrap">
                            <Checkbox
                              size="xs"
                              checked={stageEnabled}
                              onChange={e => {
                                const stages = [...pipelineConfig.stages];
                                stages[idx] = { ...stages[idx], enabled: e.currentTarget.checked };
                                setPipelineConfig({ stages });
                              }}
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
                                  onChange={e => {
                                    const stages = [...pipelineConfig.stages];
                                    stages[idx] = { ...stages[idx], name: e.currentTarget.value };
                                    setPipelineConfig({ stages });
                                  }}
                                  styles={stageEnabled ? undefined : { input: { textDecoration: "line-through" } }}
                                  w={150}
                                />
                                <NumberInput
                                  size="xs"
                                  placeholder="Max steps"
                                  title="Max agent steps"
                                  value={stage.max_agent_steps ?? 10}
                                  onChange={v => {
                                    const stages = [...pipelineConfig.stages];
                                    stages[idx] = {
                                      ...stages[idx],
                                      max_agent_steps: typeof v === "number" ? v : 10,
                                    };
                                    setPipelineConfig({ stages });
                                  }}
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
                              data={enabledModels.map(m => ({ value: m.model_id, label: m.model_id }))}
                              value={stage.model_id ?? null}
                              onChange={v => {
                                const stages = [...pipelineConfig.stages];
                                stages[idx] = { ...stages[idx], model_id: v };
                                setPipelineConfig({ stages });
                              }}
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
                              onClick={() => {
                                const stages = [...pipelineConfig.stages];
                                [stages[idx - 1], stages[idx]] = [stages[idx], stages[idx - 1]];
                                setPipelineConfig({ stages });
                              }}
                            >
                              <IconArrowUp size={14} />
                            </ActionIcon>
                            <ActionIcon
                              variant="subtle"
                              size="sm"
                              disabled={idx === pipelineConfig.stages.length - 1}
                              onClick={() => {
                                const stages = [...pipelineConfig.stages];
                                [stages[idx], stages[idx + 1]] = [stages[idx + 1], stages[idx]];
                                setPipelineConfig({ stages });
                              }}
                            >
                              <IconArrowDown size={14} />
                            </ActionIcon>
                            <ActionIcon
                              variant="subtle"
                              size="sm"
                              title={mode === "shadow" ? "Save the clone first to edit stage prompts" : "Edit Prompt"}
                              disabled={mode === "shadow"}
                              onClick={() => {
                                if (mode === "shadow" || !pipelineId) return;
                                window.location.href = `/admin/pipelines/${pipelineId}/stage/${idx}`;
                              }}
                            >
                              <IconSparkles size={14} />
                            </ActionIcon>
                            <ActionIcon
                              variant="subtle"
                              size="sm"
                              color="red"
                              onClick={() => {
                                const stages = pipelineConfig.stages.filter((_, i) => i !== idx);
                                setPipelineConfig({ stages });
                              }}
                            >
                              <IconTrash size={14} />
                            </ActionIcon>
                          </Group>
                        </Group>
                        {configOptions && (
                          <MultiSelect
                            size="xs"
                            placeholder="Select tools..."
                            data={toolsData}
                            value={stage.tools || []}
                            onChange={v => {
                              const stages = [...pipelineConfig.stages];
                              stages[idx] = { ...stages[idx], tools: v };
                              setPipelineConfig({ stages });
                            }}
                            searchable
                            clearable
                          />
                        )}
                        {stage.prompt ? (
                          <div
                            style={{
                              cursor: "pointer",
                              overflow: "hidden",
                              maxHeight: expandedStages.has(idx) ? undefined : "7.5em",
                              position: "relative",
                              fontSize: "var(--mantine-font-size-sm)",
                              color: "var(--mantine-color-dimmed)",
                            }}
                            onClick={() => setExpandedStages(prev => {
                              const next = new Set(prev);
                              if (next.has(idx)) next.delete(idx); else next.add(idx);
                              return next;
                            })}
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

          {kind === "agentic" && (
            <Alert color="blue">Agent configuration coming soon</Alert>
          )}
        </Stack>
      </Paper>
    </Container>
  );
}
