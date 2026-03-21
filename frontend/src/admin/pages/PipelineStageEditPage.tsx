import { useCallback, useEffect, useState } from "react";
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
import type { PipelineConfig } from "../../types/world";
import { LlmChatPanel } from "../components/LlmChatPanel";
import { getWorld, updateWorld } from "../../api/worlds";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractIds(): { worldId: string; stageIndex: number } | null {
  const m = window.location.pathname.match(/\/admin\/worlds\/(\d+)\/pipeline\/(\d+)/);
  if (!m) return null;
  return { worldId: m[1], stageIndex: parseInt(m[2]) };
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

  const load = useCallback(async () => {
    if (!worldId) return;
    setLoading(true);
    setError(null);
    try {
      const world = await getWorld(worldId);
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

  const isDirty = content !== originalContent;

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
            onClick={() => { window.location.href = `/admin/worlds/${worldId}/edit`; }}
          >
            Back
          </Button>
          <Title order={4}>
            <Text span c="dimmed" size="sm" mr={6}>Pipeline stage {stageIndex + 1}</Text>
            <Badge variant="light">{stepType}</Badge>
          </Title>
        </Group>
        {isDirty && <Button onClick={handleApply} loading={saving}>Apply</Button>}
      </Group>

      {error && <Alert color="red" mb="md">{error}</Alert>}
      {success && <Alert color="green" mb="md">{success}</Alert>}

      <Stack gap="md">
        {/* Prompt textarea */}
        <Textarea
          value={content}
          onChange={(e) => setContent(e.currentTarget.value)}
          autosize
          minRows={12}
          maxRows={40}
          styles={{ input: { fontFamily: "monospace" } }}
        />

        {/* LLM chat panel */}
        <LlmChatPanel
          currentContent={content}
          worldId={worldId}
          fieldType="system_prompt"
          onApply={(text) => setContent(text)}
          onAppend={(text) => setContent((prev) => prev + "\n\n" + text)}
        />
      </Stack>
    </Container>
  );
}
