import { authRequest } from "./request";
import type {
  AvailableModelsResponse,
  CreateLlmServerRequest,
  LlmServerItem,
  LlmServersListResponse,
  UpdateLlmServerRequest,
} from "../types/llmServer";

const BASE = "/api/admin/llm-servers";

export async function listServers(): Promise<LlmServerItem[]> {
  const res = await authRequest<LlmServersListResponse>(BASE);
  return res.items;
}

export async function createServer(
  data: CreateLlmServerRequest,
): Promise<LlmServerItem> {
  return authRequest<LlmServerItem>(BASE, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateServer(
  id: string,
  data: UpdateLlmServerRequest,
): Promise<LlmServerItem> {
  return authRequest<LlmServerItem>(`${BASE}/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteServer(id: string): Promise<void> {
  return authRequest<void>(`${BASE}/${id}`, {
    method: "DELETE",
  });
}

export async function probeModels(id: string): Promise<string[]> {
  const res = await authRequest<AvailableModelsResponse>(
    `${BASE}/${id}/available-models`,
  );
  return res.models;
}

export async function setEnabledModels(
  id: string,
  models: string[],
): Promise<LlmServerItem> {
  return authRequest<LlmServerItem>(`${BASE}/${id}/enabled-models`, {
    method: "PUT",
    body: JSON.stringify({ enabled_models: models }),
  });
}
