import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Container,
  Divider,
  Group,
  Select,
  Slider,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import ReactMarkdown from "react-markdown";
import type { EnabledModelInfo } from "../../types/llmServer";
import { saveToolModel, saveTextModel } from "../../utils/modelSettings";
import {
  CharacterSetupPageState,
  loadCharacterSetup,
  submitCharacter,
} from "./characterSetupPageState";

const ModelSection = observer(function ModelSection({
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
});

interface CharacterSetupPageProps {
  worldId: string;
}

export const CharacterSetupPage = observer(function CharacterSetupPage({
  worldId,
}: CharacterSetupPageProps) {
  const [state] = useState(() => new CharacterSetupPageState(worldId));
  const navigate = useNavigate();

  useEffect(() => {
    const ctrl = new AbortController();
    loadCharacterSetup(state, ctrl.signal);
    return () => ctrl.abort();
  }, []);

  async function handleSubmit() {
    if (!state.canSubmit) return;
    const ctrl = new AbortController();
    const sessionId = await submitCharacter(state, ctrl.signal);
    if (sessionId !== null) {
      navigate(`/chat/${sessionId}`);
    }
  }

  if (state.world === null) {
    return (
      <Container size="md" py="md">
        {state.worldStatus === "error" ? (
          <Text c="red">{state.worldError}</Text>
        ) : (
          <Text c="dimmed">Loading…</Text>
        )}
      </Container>
    );
  }

  const world = state.world;
  return (
    <Container size="md" py="md">
      <Title order={3} mb="xs">{world.name}</Title>
      <div className="md-body" style={{ color: "var(--mantine-color-dimmed)", marginBottom: "var(--mantine-spacing-md)", fontSize: "var(--mantine-font-size-sm)" }}>
        <ReactMarkdown>{world.description || "No description."}</ReactMarkdown>
      </div>

      <Divider label="Character" mb="md" />
      <Stack gap="sm" mb="md">
        {state.placeholders.map((ph) => (
          <TextInput
            key={ph}
            label={ph.charAt(0) + ph.slice(1).toLowerCase().replace(/_/g, " ")}
            value={state.variables[ph] ?? ""}
            onChange={(e) => { state.variables = { ...state.variables, [ph]: e.target.value }; }}
          />
        ))}
        <Select
          label="Starting location"
          value={state.locationId}
          data={world.locations.map((l) => ({ value: l.id, label: l.name }))}
          onChange={(v) => { state.locationId = v ?? ""; }}
        />
      </Stack>

      <Divider label="Tooling model" mb="md" />
      <ModelSection
        label="Tooling model"
        model={state.toolModel}
        onChange={(m) => { state.toolModel = m; saveToolModel(m); }}
        availableModels={state.availableModels}
      />

      <Divider label="Text model" my="md" />
      <ModelSection
        label="Text model"
        model={state.textModel}
        onChange={(m) => { state.textModel = m; saveTextModel(m); }}
        availableModels={state.availableModels}
      />

      {state.submitError && <Text c="red" size="sm" mt="md">{state.submitError}</Text>}

      <Group justify="flex-end" mt="lg">
        <Button
          onClick={handleSubmit}
          loading={state.submitStatus === "loading"}
          disabled={!state.canSubmit}
        >
          Start Adventure
        </Button>
      </Group>
    </Container>
  );
});
