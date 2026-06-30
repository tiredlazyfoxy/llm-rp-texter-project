import { useEffect, useState } from "react";
import {
  Button,
  Divider,
  Drawer,
  Group,
  Select,
  Slider,
  Stack,
  Switch,
  Text,
  Textarea,
  TextInput,
} from "@mantine/core";
import { observer } from "mobx-react-lite";
import {
  ChatPageState,
  loadTuningProfile,
  revertTuningProfile,
  saveTuningProfile,
  toggleDebugMode,
  updateSettings,
} from "../../pages/chatPageState";
import { request } from "../../../api/client";
import { getCurrentUser } from "../../../auth";
import { saveToolModel, saveTextModel } from "../../../utils/modelSettings";

interface EnabledModelInfo {
  server_id: string;
  server_name: string;
  model_id: string;
}

interface ChatSettingsPanelProps {
  state: ChatPageState;
  opened: boolean;
  onClose: () => void;
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
      <Text size="sm" fw={500}>{label}</Text>
      <Select
        label="Model"
        value={model.model_id}
        data={availableModels.map((m) => ({ value: m.model_id, label: `${m.model_id} (${m.server_name})` }))}
        onChange={(v) => onChange({ ...model, model_id: v })}
        clearable
        size="xs"
      />
      <Text size="xs" c="dimmed">Temperature: {model.temperature.toFixed(2)}</Text>
      <Slider
        size="xs"
        min={0} max={2} step={0.05}
        value={model.temperature}
        onChange={(v) => onChange({ ...model, temperature: v })}
        label={(v) => v.toFixed(2)}
      />
      <Text size="xs" c="dimmed">Repeat penalty: {model.repeat_penalty.toFixed(2)}</Text>
      <Slider
        size="xs"
        min={0.5} max={2} step={0.05}
        value={model.repeat_penalty}
        onChange={(v) => onChange({ ...model, repeat_penalty: v })}
        label={(v) => v.toFixed(2)}
      />
      <Text size="xs" c="dimmed">Top-p: {model.top_p.toFixed(2)}</Text>
      <Slider
        size="xs"
        min={0} max={1} step={0.05}
        value={model.top_p}
        onChange={(v) => onChange({ ...model, top_p: v })}
        label={(v) => v.toFixed(2)}
      />
    </Stack>
  );
}

export const ChatSettingsPanel = observer(function ChatSettingsPanel({ state, opened, onClose }: ChatSettingsPanelProps) {
  const session = state.currentChat?.session;
  const [toolModel, setToolModel] = useState<ModelConfig>(session?.tool_model ?? { model_id: null, temperature: 0.7, repeat_penalty: 1.0, top_p: 1.0 });
  const [textModel, setTextModel] = useState<ModelConfig>(session?.text_model ?? { model_id: null, temperature: 0.7, repeat_penalty: 1.0, top_p: 1.0 });
  const [characterName, setCharacterName] = useState<string>(session?.character_name ?? "");
  const [availableModels, setAvailableModels] = useState<EnabledModelInfo[]>([]);
  const [saving, setSaving] = useState(false);
  const [planTuning, setPlanTuning] = useState("");
  const [toneTuning, setToneTuning] = useState("");
  const [tuningSaving, setTuningSaving] = useState(false);

  const role = getCurrentUser()?.role;
  const isEditor = role === "editor" || role === "admin";
  const isChainMode = state.world?.generation_mode === "chain";
  const showTuning = isEditor && isChainMode;

  useEffect(() => {
    if (opened && session) {
      setToolModel(session.tool_model);
      setTextModel(session.text_model);
      setCharacterName(session.character_name);
      request<{ models: EnabledModelInfo[] }>("/api/chats/models")
        .then((res) => setAvailableModels(res.models))
        .catch(() => {});
    }
  }, [opened, session?.id]);

  // Load the tuning profile when the panel opens in chain mode, if not already loaded.
  useEffect(() => {
    if (opened && showTuning && !state.tuningProfile) {
      loadTuningProfile(state).catch(() => {});
    }
  }, [opened, showTuning]);

  // Reseed editable copies from the live profile (also picks up `tuning_update`).
  useEffect(() => {
    setPlanTuning(state.tuningProfile?.plan_tuning ?? "");
    setToneTuning(state.tuningProfile?.tone_tuning ?? "");
  }, [opened, state.tuningProfile?.plan_tuning, state.tuningProfile?.tone_tuning]);

  async function handleSaveTuning() {
    setTuningSaving(true);
    try {
      await saveTuningProfile(state, { plan_tuning: planTuning, tone_tuning: toneTuning });
    } finally {
      setTuningSaving(false);
    }
  }

  async function handleRevertTuning() {
    await revertTuningProfile(state);
  }

  const trimmedCharacterName = characterName.trim();
  const canSave = trimmedCharacterName !== "";

  async function handleSave() {
    if (!canSave) return;
    setSaving(true);
    saveToolModel(toolModel);
    saveTextModel(textModel);
    await updateSettings(state, {
      tool_model: toolModel,
      text_model: textModel,
      character_name: trimmedCharacterName,
    });
    setSaving(false);
    onClose();
  }

  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      title="Chat Settings"
      position="right"
      size="sm"
    >
      <Stack gap="md">
        <TextInput
          label="Character Name"
          required
          value={characterName}
          onChange={(e) => setCharacterName(e.currentTarget.value)}
        />
        <Divider />
        <ModelSection
          label="Tooling model"
          model={toolModel}
          onChange={setToolModel}
          availableModels={availableModels}
        />
        <Divider />
        <ModelSection
          label="Text model"
          model={textModel}
          onChange={setTextModel}
          availableModels={availableModels}
        />
        <Divider />
        <Button onClick={handleSave} loading={saving} disabled={!canSave}>Save</Button>

        {isEditor && (
          <>
            <Divider />
            <Switch
              label="Debug mode"
              description="Show tool calls, thinking, generation plans"
              checked={state.debugMode}
              onChange={() => toggleDebugMode(state)}
            />
          </>
        )}

        {showTuning && (
          <>
            <Divider />
            <Text size="sm" fw={500}>Preference tuning</Text>
            <Text size="xs" c="dimmed">
              Learned plan/tone guidance injected into chain generation. Updates
              automatically as you accept and reject generations.
            </Text>
            <Textarea
              label="Plan tuning"
              value={planTuning}
              onChange={(e) => setPlanTuning(e.currentTarget.value)}
              minRows={3}
              maxRows={10}
              autosize
              size="xs"
            />
            <Textarea
              label="Tone tuning"
              value={toneTuning}
              onChange={(e) => setToneTuning(e.currentTarget.value)}
              minRows={3}
              maxRows={10}
              autosize
              size="xs"
            />
            <Group gap="xs">
              <Button size="xs" onClick={handleSaveTuning} loading={tuningSaving}>Save</Button>
              <Button size="xs" variant="subtle" onClick={handleRevertTuning} disabled={tuningSaving}>
                Revert
              </Button>
            </Group>
          </>
        )}
      </Stack>
    </Drawer>
  );
});
