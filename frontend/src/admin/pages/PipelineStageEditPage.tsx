import { useCallback, useEffect, useRef, useState } from "react";
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
  Textarea,
  Title,
} from "@mantine/core";
import { IconArrowLeft } from "@tabler/icons-react";
import { fetchEnabledModels } from "../../api/llmChat";
import type { EnabledModelInfo } from "../../types/llmServer";
import type { PipelineConfig, PipelineConfigOptions } from "../../types/pipeline";
import { LlmChatPanel } from "../components/LlmChatPanel";
import { PlaceholderPanel } from "../components/PlaceholderPanel";
import { PlaceholderSuggestions } from "../components/PlaceholderSuggestions";
import { usePlaceholderAutocomplete } from "../hooks/usePlaceholderAutocomplete";
import {
  getPipeline,
  getPipelineConfigOptions,
  updatePipeline,
} from "../../api/pipelines";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractIds(): { pipelineId: string; stageIndex: number } | null {
  const m = window.location.pathname.match(/\/admin\/pipelines\/(\d+)\/stage\/(\d+)/);
  if (!m) return null;
  return { pipelineId: m[1], stageIndex: parseInt(m[2]) };
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function PipelineStageEditPage() {
  const ids = extractIds();
  const pipelineId = ids?.pipelineId ?? "";
  const stageIndex = ids?.stageIndex ?? 0;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [content, setContent] = useState("");
  const [originalContent, setOriginalContent] = useState("");
  const [pipelineConfig, setPipelineConfig] = useState<PipelineConfig>({ stages: [] });
  const [stepType, setStepType] = useState("");
  const [stageName, setStageName] = useState("");
  const [stageTools, setStageTools] = useState<string[]>([]);
  const [stageEnabled, setStageEnabled] = useState(true);
  const [stageModelId, setStageModelId] = useState<string | null>(null);
  const [configOptions, setConfigOptions] = useState<PipelineConfigOptions | null>(null);
  const [enabledModels, setEnabledModels] = useState<EnabledModelInfo[]>([]);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const autocomplete = usePlaceholderAutocomplete(
    configOptions?.placeholders ?? [], textareaRef, content, setContent,
  );

  const load = useCallback(async () => {
    if (!pipelineId) return;
    setLoading(true);
    setError(null);
    try {
      const [p, opts] = await Promise.all([
        getPipeline(pipelineId),
        getPipelineConfigOptions(),
      ]);
      setConfigOptions(opts);
      const parsed: PipelineConfig = JSON.parse(p.pipeline_config || "{}");
      const config = { stages: parsed.stages || [] };
      setPipelineConfig(config);
      if (stageIndex >= config.stages.length) {
        setError(`Stage ${stageIndex} not found`);
        return;
      }
      const stage = config.stages[stageIndex];
      setContent(stage.prompt);
      setOriginalContent(stage.prompt);
      setStepType(stage.step_type);
      setStageName(stage.name || "");
      setStageTools(stage.tools || []);
      setStageEnabled(stage.enabled !== false);
      setStageModelId(stage.model_id ?? null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [pipelineId, stageIndex]);

  useEffect(() => {
    void load();
    fetchEnabledModels().then(setEnabledModels).catch(() => {});
  }, [load]);

  const handleApply = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated: PipelineConfig = {
        stages: pipelineConfig.stages.map((s, i) =>
          i === stageIndex
            ? { ...s, prompt: content, enabled: stageEnabled, model_id: stageModelId }
            : s,
        ),
      };
      await updatePipeline(pipelineId, { pipeline_config: JSON.stringify(updated) });
      setPipelineConfig(updated);
      setOriginalContent(content);
      setSuccess("Applied.");
      setTimeout(() => setSuccess(null), 3000);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  const insertPlaceholder = (name: string) => {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const text = `{${name}}`;
    const newContent = content.slice(0, start) + text + content.slice(end);
    setContent(newContent);
    requestAnimationFrame(() => {
      ta.selectionStart = ta.selectionEnd = start + text.length;
      ta.focus();
    });
  };

  const loadDefaultTemplate = () => {
    if (!configOptions) return;
    const templates = configOptions.default_templates;
    const isToolStep = stepType === "tool" || stepType === "planning";
    const template = isToolStep ? templates.tool : templates.writer;
    if (content && !window.confirm("Replace current content with default template?")) return;
    setContent(template);
  };

  const originalStage = pipelineConfig.stages[stageIndex];
  const isDirty =
    content !== originalContent ||
    (originalStage && (originalStage.enabled !== false) !== stageEnabled) ||
    (originalStage && (originalStage.model_id ?? null) !== stageModelId);

  if (loading) {
    return (
      <Container pt="xl">
        <Loader />
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
            onClick={() => { window.location.href = `/admin/pipelines/${pipelineId}`; }}
          >
            Back
          </Button>
          <Title order={4}>
            <Text span c="dimmed" size="sm" mr={6}>Pipeline stage {stageIndex + 1}</Text>
            {stageName && <Text span size="sm" fw={600} mr={6}>{stageName}</Text>}
            <Badge variant="light" color={(stepType === "tool" || stepType === "planning") ? "violet" : "teal"}>
              {stepType}
            </Badge>
          </Title>
        </Group>
        <Group>
          {configOptions && (
            <Button variant="default" size="compact-sm" onClick={loadDefaultTemplate}>
              Load Default Template
            </Button>
          )}
          {isDirty && <Button onClick={handleApply} loading={saving}>Apply</Button>}
        </Group>
      </Group>

      {error && <Alert color="red" mb="md">{error}</Alert>}
      {success && <Alert color="green" mb="md">{success}</Alert>}

      <Paper p="sm" withBorder mb="md">
        <Group gap="md" wrap="nowrap">
          <Checkbox
            label="Stage enabled"
            checked={stageEnabled}
            onChange={e => setStageEnabled(e.currentTarget.checked)}
          />
          <Select
            label="Model override"
            description="Leave empty to use the session model"
            placeholder="Session model"
            data={enabledModels.map(m => ({ value: m.model_id, label: m.model_id }))}
            value={stageModelId}
            onChange={setStageModelId}
            searchable
            clearable
            w={320}
          />
        </Group>
      </Paper>

      <Stack gap="md">
        {/* Prompt textarea */}
        <div style={{ height: "60vh", overflow: "auto", resize: "vertical" }}>
          <Textarea
            ref={textareaRef}
            value={content}
            onChange={(e) => {
              setContent(e.currentTarget.value);
              autocomplete.onTextChange(e.currentTarget.value, e.currentTarget);
            }}
            onKeyDown={autocomplete.onKeyDown}
            autosize
            minRows={12}
            styles={{ input: { fontFamily: "monospace" } }}
          />
        </div>
        <PlaceholderSuggestions
          visible={autocomplete.visible}
          suggestions={autocomplete.suggestions}
          selectedIndex={autocomplete.selectedIndex}
          position={autocomplete.position}
          onSelect={autocomplete.onSelect}
        />

        {/* Placeholder reference panel */}
        {configOptions && (
          <PlaceholderPanel
            placeholders={configOptions.placeholders}
            content={content}
            onInsert={insertPlaceholder}
          />
        )}

        {/* Enabled tools for this stage (read-only) */}
        {stageTools.length > 0 && (
          <Paper p="sm" withBorder>
            <Text size="sm" fw={500} mb="xs">Enabled Tools</Text>
            <Group gap="xs">
              {stageTools.map(t => (
                <Badge key={t} size="sm" variant="light">{t}</Badge>
              ))}
            </Group>
          </Paper>
        )}

        {/* LLM chat panel — world-agnostic for pipeline prompts (no worldId passed) */}
        <LlmChatPanel
          currentContent={content}
          fieldType="pipeline_prompt"
          onApply={(text) => setContent(text)}
          onAppend={(text) => setContent((prev) => prev + "\n\n" + text)}
        />
      </Stack>
    </Container>
  );
}
