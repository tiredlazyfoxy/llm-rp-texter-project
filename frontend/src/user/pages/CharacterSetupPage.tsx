import { useEffect, useState } from "react";
import {
  Button,
  Container,
  Divider,
  Group,
  NumberInput,
  Select,
  Slider,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { listPublicWorlds, createChat } from "../../api/chat";
import { authRequest } from "../../api/request";
import { loadToolModel, loadTextModel, saveToolModel, saveTextModel } from "../../utils/modelSettings";

interface EnabledModelInfo {
  server_id: string;
  server_name: string;
  model_id: string;
}

function _worldIdFromPath(): string {
  const match = window.location.pathname.match(/\/worlds\/(\d+)\/new/);
  return match?.[1] ?? "";
}

function ModelSection({
  label,
  model,
  onChange,
  availableModels,
}: {
  label: string;
  model: ModelConfig;
  onChange: (m: ModelConfig) => void;
  availableModels: EnabledModelInfo[];
}) {
  return (
    <Stack gap="xs">
      <Text fw={500} size="sm">{label}</Text>
      <Select
        label="Model"
        placeholder="Select model"
        value={model.model_id}
        data={availableModels.map((m) => ({ value: m.model_id, label: `${m.model_id} (${m.server_name})` }))}
        onChange={(v) => onChange({ ...model, model_id: v })}
        clearable
      />
      <Text size="xs" c="dimmed">Temperature: {model.temperature.toFixed(2)}</Text>
      <Slider
        min={0} max={2} step={0.05} value={model.temperature}
        onChange={(v) => onChange({ ...model, temperature: v })}
        label={(v) => v.toFixed(2)}
      />
      <Text size="xs" c="dimmed">Repeat penalty: {model.repeat_penalty.toFixed(2)}</Text>
      <Slider
        min={0.5} max={2} step={0.05} value={model.repeat_penalty}
        onChange={(v) => onChange({ ...model, repeat_penalty: v })}
        label={(v) => v.toFixed(2)}
      />
      <Text size="xs" c="dimmed">Top-p: {model.top_p.toFixed(2)}</Text>
      <Slider
        min={0} max={1} step={0.05} value={model.top_p}
        onChange={(v) => onChange({ ...model, top_p: v })}
        label={(v) => v.toFixed(2)}
      />
    </Stack>
  );
}

export function CharacterSetupPage() {
  const worldId = _worldIdFromPath();
  const [world, setWorld] = useState<WorldInfo | null>(null);
  const [availableModels, setAvailableModels] = useState<EnabledModelInfo[]>([]);
  const [placeholders, setPlaceholders] = useState<string[]>([]);
  const [variables, setVariables] = useState<Record<string, string>>({});
  const [locationId, setLocationId] = useState<string>("");
  const [toolModel, setToolModel] = useState<ModelConfig>(loadToolModel);
  const [textModel, setTextModel] = useState<ModelConfig>(loadTextModel);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listPublicWorlds().then((worlds) => {
      const w = worlds.find((w) => w.id === worldId);
      if (!w) return;
      setWorld(w);
      // Extract {PLACEHOLDER} tokens
      const phs = [...new Set([...w.character_template.matchAll(/\{([A-Z_]+)\}/g)].map((m) => m[1]))];
      setPlaceholders(phs);
      setVariables(Object.fromEntries(phs.map((p) => [p, ""])));
      if (w.locations.length > 0) setLocationId(w.locations[0].id);
    }).catch(() => {});

    authRequest<{ models: EnabledModelInfo[] }>("/api/chats/models").then((res) => {
      setAvailableModels(res.models);
      if (res.models.length > 0) {
        const ids = res.models.map((m) => m.model_id);
        // If saved model_id is not in available list, fall back to first
        setToolModel((prev) => ids.includes(prev.model_id ?? "") ? prev : { ...prev, model_id: res.models[0].model_id });
        setTextModel((prev) => ids.includes(prev.model_id ?? "") ? prev : { ...prev, model_id: res.models[0].model_id });
      }
    }).catch(() => {});
  }, [worldId]);

  async function handleSubmit() {
    if (!world) return;
    setError(null);
    setSubmitting(true);
    try {
      const session = await createChat({
        world_id: worldId,
        character_name: variables["NAME"] || variables[placeholders[0]] || "Hero",
        template_variables: variables,
        starting_location_id: locationId,
        tool_model: toolModel,
        text_model: textModel,
      });
      window.location.href = `/chat/${session.id}`;
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  if (!world) return <Container size="md" py="md"><Text c="dimmed">Loading…</Text></Container>;

  return (
    <Container size="md" py="md">
      <Title order={3} mb="xs">{world.name}</Title>
      <Text size="sm" c="dimmed" mb="md">{world.description}</Text>

      <Divider label="Character" mb="md" />
      <Stack gap="sm" mb="md">
        {placeholders.map((ph) => (
          <TextInput
            key={ph}
            label={ph.charAt(0) + ph.slice(1).toLowerCase().replace(/_/g, " ")}
            value={variables[ph] ?? ""}
            onChange={(e) => setVariables((prev) => ({ ...prev, [ph]: e.target.value }))}
          />
        ))}
        <Select
          label="Starting location"
          value={locationId}
          data={world.locations.map((l) => ({ value: l.id, label: l.name }))}
          onChange={(v) => setLocationId(v ?? "")}
        />
      </Stack>

      <Divider label="Tooling model" mb="md" />
      <ModelSection
        label="Tooling model"
        model={toolModel}
        onChange={(m) => { setToolModel(m); saveToolModel(m); }}
        availableModels={availableModels}
      />

      <Divider label="Text model" my="md" />
      <ModelSection
        label="Text model"
        model={textModel}
        onChange={(m) => { setTextModel(m); saveTextModel(m); }}
        availableModels={availableModels}
      />

      {error && <Text c="red" size="sm" mt="md">{error}</Text>}

      <Group justify="flex-end" mt="lg">
        <Button onClick={handleSubmit} loading={submitting}>
          Start Adventure
        </Button>
      </Group>
    </Container>
  );
}
