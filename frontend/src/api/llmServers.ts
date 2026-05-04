import { request } from "./client";
import type {
  AvailableModelsResponse,
  CreateLlmServerRequest,
  LlmServerItem,
  LlmServersListResponse,
  UpdateLlmServerRequest,
} from "../types/llmServer";

const BASE = "/api/admin/llm-servers";

export async function listServers(signal?: AbortSignal): Promise<LlmServerItem[]> {
  const res = await request<LlmServersListResponse>(BASE, { signal });
  return res.items;
}

export async function createServer(
  data: CreateLlmServerRequest,
  signal?: AbortSignal,
): Promise<LlmServerItem> {
  return request<LlmServerItem>(BASE, {
    method: "POST",
    body: data,
    signal,
  });
}

export async function updateServer(
  id: string,
  data: UpdateLlmServerRequest,
  signal?: AbortSignal,
): Promise<LlmServerItem> {
  return request<LlmServerItem>(`${BASE}/${id}`, {
    method: "PUT",
    body: data,
    signal,
  });
}

export async function deleteServer(id: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/${id}`, {
    method: "DELETE",
    signal,
  });
}

export async function probeModels(id: string, signal?: AbortSignal): Promise<string[]> {
  const res = await request<AvailableModelsResponse>(
    `${BASE}/${id}/available-models`,
    { signal },
  );
  return res.models;
}

export async function setEnabledModels(
  id: string,
  models: string[],
  signal?: AbortSignal,
): Promise<LlmServerItem> {
  return request<LlmServerItem>(`${BASE}/${id}/enabled-models`, {
    method: "PUT",
    body: { enabled_models: models },
    signal,
  });
}

export async function setEmbedding(
  id: string,
  model: string,
  signal?: AbortSignal,
): Promise<LlmServerItem> {
  return request<LlmServerItem>(`${BASE}/${id}/embedding`, {
    method: "PUT",
    body: { model },
    signal,
  });
}

export async function clearEmbedding(signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/embedding`, {
    method: "DELETE",
    signal,
  });
}
