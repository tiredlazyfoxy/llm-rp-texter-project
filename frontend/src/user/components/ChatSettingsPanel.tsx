import { useEffect, useState } from "react";
import {
  Button,
  Divider,
  Drawer,
  Select,
  Slider,
  Stack,
  Text,
  Textarea,
} from "@mantine/core";
import { observer } from "mobx-react-lite";
import { chatStore } from "../stores/ChatStore";
import { authRequest } from "../../api/request";

interface EnabledModelInfo {
  server_id: string;
  server_name: string;
  model_id: string;
}

interface ChatSettingsPanelProps {
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

export const ChatSettingsPanel = observer(function ChatSettingsPanel({ opened, onClose }: ChatSettingsPanelProps) {
  const session = chatStore.currentChat?.session;
  const [toolModel, setToolModel] = useState<ModelConfig>(session?.tool_model ?? { model_id: null, temperature: 0.7, repeat_penalty: 1.0, top_p: 1.0 });
  const [textModel, setTextModel] = useState<ModelConfig>(session?.text_model ?? { model_id: null, temperature: 0.7, repeat_penalty: 1.0, top_p: 1.0 });
  const [instructions, setInstructions] = useState(session?.user_instructions ?? "");
  const [availableModels, setAvailableModels] = useState<EnabledModelInfo[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (opened && session) {
      setToolModel(session.tool_model);
      setTextModel(session.text_model);
      setInstructions(session.user_instructions);
      authRequest<{ models: EnabledModelInfo[] }>("/api/chats/models")
        .then((res) => setAvailableModels(res.models))
        .catch(() => {});
    }
  }, [opened, session?.id]);

  async function handleSave() {
    setSaving(true);
    await chatStore.updateSettings({ tool_model: toolModel, text_model: textModel, user_instructions: instructions });
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
        <Textarea
          label="User instructions"
          description="Appended to the system prompt"
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          minRows={3}
          maxRows={8}
          autosize
        />
        <Button onClick={handleSave} loading={saving}>Save</Button>
      </Stack>
    </Drawer>
  );
});
