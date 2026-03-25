import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  Textarea,
  Title,
  Tooltip,
} from "@mantine/core";
import { IconArrowLeft } from "@tabler/icons-react";
import type { PipelineConfig, PipelineConfigOptions } from "../../types/world";
import { LlmChatPanel } from "../components/LlmChatPanel";
import { getPipelineConfigOptions, getWorld, updateWorld } from "../../api/worlds";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractIds(): { worldId: string; stageIndex: number } | null {
  const m = window.location.pathname.match(/\/admin\/worlds\/(\d+)\/pipeline\/(\d+)/);
  if (!m) return null;
  return { worldId: m[1], stageIndex: parseInt(m[2]) };
}

/** Group items by a key function. */
function groupBy<T>(items: T[], key: (item: T) => string): Record<string, T[]> {
  const result: Record<string, T[]> = {};
  for (const item of items) {
    const k = key(item);
    (result[k] ??= []).push(item);
  }
  return result;
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function PipelineStageEditPage() {
  const ids = extractIds();
  const worldId = ids?.worldId ?? "";
  const stageIndex = ids?.stageIndex ?? 0;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [content, setContent] = useState("");
  const [originalContent, setOriginalContent] = useState("");
  const [pipelineConfig, setPipelineConfig] = useState<PipelineConfig>({ stages: [] });
  const [stepType, setStepType] = useState("");
  const [stageTools, setStageTools] = useState<string[]>([]);
  const [configOptions, setConfigOptions] = useState<PipelineConfigOptions | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const load = useCallback(async () => {
    if (!worldId) return;
    setLoading(true);
    setError(null);
    try {
      const [world, opts] = await Promise.all([
        getWorld(worldId),
        getPipelineConfigOptions(),
      ]);
      setConfigOptions(opts);
      const parsed: PipelineConfig = JSON.parse(world.pipeline || "{}");
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
      setStageTools(stage.tools || []);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [worldId, stageIndex]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleApply = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated: PipelineConfig = {
        stages: pipelineConfig.stages.map((s, i) =>
          i === stageIndex ? { ...s, prompt: content } : s
        ),
      };
      await updateWorld(worldId, { pipeline: JSON.stringify(updated) });
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

  const isDirty = content !== originalContent;

  if (loading) {
    return (
      <Container pt="xl">
        <Loader />
      </Container>
    );
  }

  const placeholderGroups = configOptions
    ? groupBy(configOptions.placeholders, p => p.category)
    : {};

  return (
    <Container size="lg" py="md">
      {/* Top bar */}
      <Group justify="space-between" mb="md">
        <Group>
          <Button
            variant="subtle"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => { window.location.href = `/admin/worlds/${worldId}/edit`; }}
          >
            Back
          </Button>
          <Title order={4}>
            <Text span c="dimmed" size="sm" mr={6}>Pipeline stage {stageIndex + 1}</Text>
            <Badge variant="light" color={(stepType === "tool" || stepType === "planning") ? "violet" : "teal"}>{stepType}</Badge>
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

      <Stack gap="md">
        {/* Prompt textarea */}
        <Textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.currentTarget.value)}
          autosize
          minRows={12}
          maxRows={40}
          styles={{ input: { fontFamily: "monospace" } }}
        />

        {/* Placeholder reference panel */}
        {configOptions && (
          <Paper p="sm" withBorder>
            <Text size="sm" fw={500} mb="xs">Placeholders (click to insert)</Text>
            <Stack gap="xs">
              {Object.entries(placeholderGroups).map(([category, placeholders]) => (
                <Group key={category} gap="xs">
                  <Text size="xs" c="dimmed" w={70}>{category}:</Text>
                  {placeholders.map(p => (
                    <Tooltip key={p.name} label={p.description} withArrow>
                      <Badge
                        size="sm"
                        variant="outline"
                        style={{ cursor: "pointer" }}
                        onClick={() => insertPlaceholder(p.name)}
                      >
                        {`{${p.name}}`}
                      </Badge>
                    </Tooltip>
                  ))}
                </Group>
              ))}
            </Stack>
          </Paper>
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

        {/* LLM chat panel */}
        <LlmChatPanel
          currentContent={content}
          worldId={worldId}
          fieldType="pipeline_prompt"
          onApply={(text) => setContent(text)}
          onAppend={(text) => setContent((prev) => prev + "\n\n" + text)}
        />
      </Stack>
    </Container>
  );
}
