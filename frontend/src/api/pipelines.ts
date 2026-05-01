import { authRequest } from "./request";
import type {
  CreatePipelineRequest,
  PipelineConfigOptions,
  PipelineItem,
  PipelinesListResponse,
  UpdatePipelineRequest,
} from "../types/pipeline";

const BASE = "/api/admin/pipelines";

export async function listPipelines(): Promise<PipelineItem[]> {
  const res = await authRequest<PipelinesListResponse>(BASE);
  return res.items;
}

export async function getPipeline(id: string): Promise<PipelineItem> {
  return authRequest<PipelineItem>(`${BASE}/${id}`);
}

export async function createPipeline(data: CreatePipelineRequest): Promise<PipelineItem> {
  return authRequest<PipelineItem>(BASE, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updatePipeline(id: string, data: UpdatePipelineRequest): Promise<PipelineItem> {
  return authRequest<PipelineItem>(`${BASE}/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deletePipeline(id: string): Promise<void> {
  return authRequest<void>(`${BASE}/${id}`, {
    method: "DELETE",
  });
}

export async function getPipelineConfigOptions(): Promise<PipelineConfigOptions> {
  return authRequest<PipelineConfigOptions>(`${BASE}/config-options`);
}
