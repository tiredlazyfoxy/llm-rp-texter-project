import type { TranslationSettings } from "../types/userSettings";
import type { EnabledModelInfo } from "../types/llmServer";
import { request } from "./client";

export async function getTranslationSettings(signal?: AbortSignal): Promise<TranslationSettings> {
  return request<TranslationSettings>("/api/settings/translation", { signal });
}

export async function updateTranslationSettings(
  settings: TranslationSettings,
  signal?: AbortSignal,
): Promise<TranslationSettings> {
  return request<TranslationSettings>("/api/settings/translation", {
    method: "PUT",
    body: settings,
    signal,
  });
}

export async function fetchModelsForSettings(signal?: AbortSignal): Promise<EnabledModelInfo[]> {
  const res = await request<{ models: EnabledModelInfo[] }>("/api/chats/models", { signal });
  return res.models;
}
