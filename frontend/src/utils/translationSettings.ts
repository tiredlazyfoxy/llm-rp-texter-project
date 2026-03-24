import type { TranslationSettings } from "../types/userSettings";
import {
  getTranslationSettings as fetchSettings,
  updateTranslationSettings as putSettings,
} from "../api/userSettings";

const DEFAULTS: TranslationSettings = {
  translate_model_id: null,
  translate_temperature: 0.1,
  translate_top_p: 1.0,
  translate_repeat_penalty: 1.0,
  translate_think: false,
};

let _settings: TranslationSettings = { ...DEFAULTS };
let _loaded = false;

/** Fetch settings from backend. Call once on app init (fire-and-forget). */
export async function loadTranslationSettings(): Promise<void> {
  try {
    _settings = await fetchSettings();
    _loaded = true;
  } catch {
    // Keep defaults if backend unreachable or no settings yet
  }
}

/** Synchronous read of cached settings. */
export function getTranslationSettings(): TranslationSettings {
  return _settings;
}

/** Whether settings have been loaded from backend. */
export function isTranslationSettingsLoaded(): boolean {
  return _loaded;
}

/** Save settings to backend and update cache. */
export async function saveTranslationSettings(s: TranslationSettings): Promise<void> {
  _settings = await putSettings(s);
  _loaded = true;
}
