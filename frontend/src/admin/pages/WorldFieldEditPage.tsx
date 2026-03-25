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
import type { PipelineConfigOptions, UpdateWorldRequest, WorldDetail } from "../../types/world";
import { LlmChatPanel } from "../components/LlmChatPanel";
import { getPipelineConfigOptions, getWorld, updateWorld } from "../../api/worlds";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type FieldName = "description" | "system_prompt" | "initial_message";

function extractIds(): { worldId: string; fieldName: FieldName } | null {
  const m = window.location.pathname.match(/\/admin\/worlds\/(\d+)\/field\/(description|system_prompt|initial_message)/);
  if (!m) return null;
  return { worldId: m[1], fieldName: m[2] as FieldName };
}

const FIELD_LABELS: Record<FieldName, string> = {
  description: "Description",
  system_prompt: "System Prompt",
  initial_message: "Initial Message",
};

function getFieldValue(world: WorldDetail, field: FieldName): string {
  if (field === "description") return world.description ?? "";
  if (field === "system_prompt") return world.system_prompt ?? "";
  if (field === "initial_message") return world.initial_message ?? "";
  return "";
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

export function WorldFieldEditPage() {
  const ids = extractIds();
  const worldId = ids?.worldId ?? "";
  const fieldName = ids?.fieldName ?? "description";

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [content, setContent] = useState("");
  const [originalContent, setOriginalContent] = useState("");
  const [configOptions, setConfigOptions] = useState<PipelineConfigOptions | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isPipelinePrompt = fieldName === "system_prompt";

  const load = useCallback(async () => {
    if (!worldId) return;
    setLoading(true);
    setError(null);
    try {
      const promises: [Promise<WorldDetail>, Promise<PipelineConfigOptions> | null] = [
        getWorld(worldId),
        isPipelinePrompt ? getPipelineConfigOptions() : null,
      ];
      const world = await promises[0];
      if (promises[1]) {
        setConfigOptions(await promises[1]);
      }
      const value = getFieldValue(world, fieldName);
      setContent(value);
      setOriginalContent(value);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [worldId, fieldName, isPipelinePrompt]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleApply = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const patch: UpdateWorldRequest = { [fieldName]: content };
      await updateWorld(worldId, patch);
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
    if (content && !window.confirm("Replace current content with default template?")) return;
    setContent(configOptions.default_templates.simple);
  };

  const isDirty = content !== originalContent;
  const label = FIELD_LABELS[fieldName];
  const fieldType = isPipelinePrompt ? "pipeline_prompt" : fieldName;

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
            onClick={() => window.history.back()}
          >
            Back
          </Button>
          <Title order={4}>
            <Text span c="dimmed" size="sm" mr={6}>World field</Text>
            <Badge variant="light">{label}</Badge>
          </Title>
        </Group>
        <Group>
          {isPipelinePrompt && configOptions && (
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
        {/* Field textarea */}
        <Textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.currentTarget.value)}
          autosize
          minRows={4}
          maxRows={30}
          styles={{ input: { fontFamily: "monospace" } }}
        />

        {/* Placeholder reference panel (system_prompt only) */}
        {isPipelinePrompt && configOptions && (
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

        {/* LLM chat panel */}
        <LlmChatPanel
          currentContent={content}
          worldId={worldId}
          fieldType={fieldType}
          onApply={(text) => setContent(text)}
          onAppend={(text) => setContent((prev) => prev + "\n\n" + text)}
        />
      </Stack>
    </Container>
  );
}
