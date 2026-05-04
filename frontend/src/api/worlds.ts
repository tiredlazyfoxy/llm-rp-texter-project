import { getToken } from "../auth";
import { request, throwApiError } from "./client";
import type {
  CreateDocumentRequest,
  CreateNpcLocationLinkRequest,
  CreateRuleRequest,
  CreateStatRequest,
  CreateWorldRequest,
  DocumentItem,
  DocumentSaveResponse,
  DocumentsListResponse,
  NpcLocationLinkItem,
  NpcLocationLinksListResponse,
  RuleItem,
  StatDefinitionItem,
  UpdateDocumentRequest,
  UpdateRuleRequest,
  UpdateStatRequest,
  UpdateWorldRequest,
  WorldDetail,
  WorldItem,
  WorldsListResponse,
} from "../types/world";

const BASE = "/api/admin/worlds";

// ── Worlds ──────────────────────────────────────────────────────

export async function listWorlds(signal?: AbortSignal): Promise<WorldItem[]> {
  const res = await request<WorldsListResponse>(BASE, { signal });
  return res.items;
}

export async function getWorld(id: string, signal?: AbortSignal): Promise<WorldDetail> {
  return request<WorldDetail>(`${BASE}/${id}`, { signal });
}

export async function createWorld(data: CreateWorldRequest, signal?: AbortSignal): Promise<WorldItem> {
  return request<WorldItem>(BASE, {
    method: "POST",
    body: data,
    signal,
  });
}

export async function updateWorld(id: string, data: UpdateWorldRequest, signal?: AbortSignal): Promise<WorldItem> {
  return request<WorldItem>(`${BASE}/${id}`, {
    method: "PUT",
    body: data,
    signal,
  });
}

export async function cloneWorld(id: string, signal?: AbortSignal): Promise<WorldItem> {
  return request<WorldItem>(`${BASE}/${id}/clone`, {
    method: "POST",
    signal,
  });
}

export async function deleteWorld(id: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/${id}`, {
    method: "DELETE",
    signal,
  });
}

export interface ReindexWorldResult {
  indexed_count: number;
  warning: string | null;
}

export async function reindexWorld(worldId: string, signal?: AbortSignal): Promise<ReindexWorldResult> {
  return request<ReindexWorldResult>(`${BASE}/${worldId}/reindex`, {
    method: "POST",
    signal,
  });
}

// ── Documents ───────────────────────────────────────────────────

export async function listDocuments(worldId: string, docType?: string, signal?: AbortSignal): Promise<DocumentItem[]> {
  const params = docType ? `?doc_type=${docType}` : "";
  const res = await request<DocumentsListResponse>(`${BASE}/${worldId}/documents${params}`, { signal });
  return res.items;
}

export async function getDocument(worldId: string, docId: string, signal?: AbortSignal): Promise<DocumentItem> {
  return request<DocumentItem>(`${BASE}/${worldId}/documents/${docId}`, { signal });
}

export async function createDocument(worldId: string, data: CreateDocumentRequest, signal?: AbortSignal): Promise<DocumentSaveResponse> {
  return request<DocumentSaveResponse>(`${BASE}/${worldId}/documents`, {
    method: "POST",
    body: data,
    signal,
  });
}

export async function updateDocument(
  worldId: string, docId: string, data: UpdateDocumentRequest, signal?: AbortSignal,
): Promise<DocumentSaveResponse> {
  return request<DocumentSaveResponse>(`${BASE}/${worldId}/documents/${docId}`, {
    method: "PUT",
    body: data,
    signal,
  });
}

export async function deleteDocument(worldId: string, docId: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/${worldId}/documents/${docId}`, {
    method: "DELETE",
    signal,
  });
}

export async function uploadDocuments(worldId: string, files: File[], docType: string, signal?: AbortSignal): Promise<DocumentSaveResponse[]> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  const token = getToken();
  const res = await fetch(`${BASE}/${worldId}/documents/upload?doc_type=${docType}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
    signal,
  });
  if (!res.ok) await throwApiError(res);
  return res.json() as Promise<DocumentSaveResponse[]>;
}

export async function downloadDocument(worldId: string, docId: string, signal?: AbortSignal): Promise<void> {
  const token = getToken();
  const res = await fetch(`${BASE}/${worldId}/documents/${docId}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  });
  if (!res.ok) await throwApiError(res);
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : "document.md";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function downloadAllDocuments(worldId: string, signal?: AbortSignal): Promise<void> {
  const token = getToken();
  const res = await fetch(`${BASE}/${worldId}/documents/download-all`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  });
  if (!res.ok) await throwApiError(res);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `world_${worldId}_documents.zip`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Stats ───────────────────────────────────────────────────────

export async function listStats(worldId: string, signal?: AbortSignal): Promise<StatDefinitionItem[]> {
  return request<StatDefinitionItem[]>(`${BASE}/${worldId}/stats`, { signal });
}

export async function createStat(worldId: string, data: CreateStatRequest, signal?: AbortSignal): Promise<StatDefinitionItem> {
  return request<StatDefinitionItem>(`${BASE}/${worldId}/stats`, {
    method: "POST",
    body: data,
    signal,
  });
}

export async function updateStat(
  worldId: string, statId: string, data: UpdateStatRequest, signal?: AbortSignal,
): Promise<StatDefinitionItem> {
  return request<StatDefinitionItem>(`${BASE}/${worldId}/stats/${statId}`, {
    method: "PUT",
    body: data,
    signal,
  });
}

export async function deleteStat(worldId: string, statId: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/${worldId}/stats/${statId}`, {
    method: "DELETE",
    signal,
  });
}

// ── Rules ───────────────────────────────────────────────────────

export async function listRules(worldId: string, signal?: AbortSignal): Promise<RuleItem[]> {
  return request<RuleItem[]>(`${BASE}/${worldId}/rules`, { signal });
}

export async function createRule(worldId: string, data: CreateRuleRequest, signal?: AbortSignal): Promise<RuleItem> {
  return request<RuleItem>(`${BASE}/${worldId}/rules`, {
    method: "POST",
    body: data,
    signal,
  });
}

export async function updateRule(
  worldId: string, ruleId: string, data: UpdateRuleRequest, signal?: AbortSignal,
): Promise<RuleItem> {
  return request<RuleItem>(`${BASE}/${worldId}/rules/${ruleId}`, {
    method: "PUT",
    body: data,
    signal,
  });
}

export async function deleteRule(worldId: string, ruleId: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/${worldId}/rules/${ruleId}`, {
    method: "DELETE",
    signal,
  });
}

export async function reorderRules(worldId: string, ruleIds: string[], signal?: AbortSignal): Promise<RuleItem[]> {
  return request<RuleItem[]>(`${BASE}/${worldId}/rules/reorder`, {
    method: "PUT",
    body: { rule_ids: ruleIds },
    signal,
  });
}

// ── NPC-Location Links ──────────────────────────────────────────

export async function listLinks(worldId: string, signal?: AbortSignal): Promise<NpcLocationLinkItem[]> {
  const res = await request<NpcLocationLinksListResponse>(`${BASE}/${worldId}/npc-location-links`, { signal });
  return res.items;
}

export async function createLink(worldId: string, data: CreateNpcLocationLinkRequest, signal?: AbortSignal): Promise<NpcLocationLinkItem> {
  return request<NpcLocationLinkItem>(`${BASE}/${worldId}/npc-location-links`, {
    method: "POST",
    body: data,
    signal,
  });
}

export async function deleteLink(worldId: string, linkId: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/${worldId}/npc-location-links/${linkId}`, {
    method: "DELETE",
    signal,
  });
}
