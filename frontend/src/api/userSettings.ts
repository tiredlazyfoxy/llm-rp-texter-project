import type { TranslationSettings } from "../types/userSettings";
import type { EnabledModelInfo } from "../types/llmServer";
import { authRequest } from "./request";

export async function getTranslationSettings(): Promise<TranslationSettings> {
  return authRequest<TranslationSettings>("/api/settings/translation");
}

export async function updateTranslationSettings(
  settings: TranslationSettings,
): Promise<TranslationSettings> {
  return authRequest<TranslationSettings>("/api/settings/translation", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

export async function fetchModelsForSettings(): Promise<EnabledModelInfo[]> {
  const res = await authRequest<{ models: EnabledModelInfo[] }>("/api/chats/models");
  return res.models;
}
