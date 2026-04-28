import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Modal,
  Select,
  Slider,
  Stack,
  Switch,
  Text,
} from "@mantine/core";
import type { EnabledModelInfo } from "../types/llmServer";
import type { TranslationSettings } from "../types/userSettings";
import { fetchModelsForSettings } from "../api/userSettings";
import {
  getTranslationSettings,
  saveTranslationSettings,
} from "../utils/translationSettings";

interface TranslationSettingsModalProps {
  opened: boolean;
  onClose: () => void;
}

export function TranslationSettingsModal({ opened, onClose }: TranslationSettingsModalProps) {
  const [models, setModels] = useState<EnabledModelInfo[]>([]);
  const [settings, setSettings] = useState<TranslationSettings>(getTranslationSettings());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (opened) {
      setSettings(getTranslationSettings());
      setError(null);
      fetchModelsForSettings()
        .then(setModels)
        .catch(() => {});
    }
  }, [opened]);

  async function handleSave() {
    setError(null);
    setLoading(true);
    try {
      await saveTranslationSettings(settings);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save settings");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Translation Settings" size="sm">
      <Stack>
        {error && (
          <Alert color="red" onClose={() => setError(null)} withCloseButton>
            {error}
          </Alert>
        )}

        <Select
          label="Translation model"
          value={settings.translate_model_id}
          data={models.map((m) => ({
            value: m.model_id,
            label: `${m.model_id} (${m.server_name})`,
          }))}
          onChange={(v) => setSettings({ ...settings, translate_model_id: v })}
          clearable
          searchable
          size="xs"
        />

        <Text size="xs" c="dimmed">Temperature: {settings.translate_temperature.toFixed(2)}</Text>
        <Slider
          size="xs"
          min={0} max={2} step={0.05}
          value={settings.translate_temperature}
          onChange={(v) => setSettings({ ...settings, translate_temperature: v })}
          label={(v) => v.toFixed(2)}
        />

        <Text size="xs" c="dimmed">Top-p: {settings.translate_top_p.toFixed(2)}</Text>
        <Slider
          size="xs"
          min={0} max={1} step={0.05}
          value={settings.translate_top_p}
          onChange={(v) => setSettings({ ...settings, translate_top_p: v })}
          label={(v) => v.toFixed(2)}
        />

        <Text size="xs" c="dimmed">Repeat penalty: {settings.translate_repeat_penalty.toFixed(2)}</Text>
        <Slider
          size="xs"
          min={0.5} max={2} step={0.05}
          value={settings.translate_repeat_penalty}
          onChange={(v) => setSettings({ ...settings, translate_repeat_penalty: v })}
          label={(v) => v.toFixed(2)}
        />

        <Switch
          label="Enable thinking"
          description="Allow model to think before translating"
          checked={settings.translate_think}
          onChange={(e) => setSettings({ ...settings, translate_think: e.currentTarget.checked })}
        />

        <Button onClick={handleSave} loading={loading}>
          Save
        </Button>
      </Stack>
    </Modal>
  );
}
