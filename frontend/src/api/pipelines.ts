import { request } from "./client";
import type {
  CreatePipelineRequest,
  PipelineConfigOptions,
  PipelineItem,
  PipelinesListResponse,
  UpdatePipelineRequest,
} from "../types/pipeline";

const BASE = "/api/admin/pipelines";

export async function listPipelines(signal?: AbortSignal): Promise<PipelineItem[]> {
  const res = await request<PipelinesListResponse>(BASE, { signal });
  return res.items;
}

export async function getPipeline(id: string, signal?: AbortSignal): Promise<PipelineItem> {
  return request<PipelineItem>(`${BASE}/${id}`, { signal });
}

export async function createPipeline(data: CreatePipelineRequest, signal?: AbortSignal): Promise<PipelineItem> {
  return request<PipelineItem>(BASE, {
    method: "POST",
    body: data,
    signal,
  });
}

export async function updatePipeline(id: string, data: UpdatePipelineRequest, signal?: AbortSignal): Promise<PipelineItem> {
  return request<PipelineItem>(`${BASE}/${id}`, {
    method: "PUT",
    body: data,
    signal,
  });
}

export async function deletePipeline(id: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/${id}`, {
    method: "DELETE",
    signal,
  });
}

export async function getPipelineConfigOptions(signal?: AbortSignal): Promise<PipelineConfigOptions> {
  return request<PipelineConfigOptions>(`${BASE}/config-options`, { signal });
}
