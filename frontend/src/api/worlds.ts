import { getToken } from "../auth";
import { authRequest } from "./request";
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

export async function listWorlds(): Promise<WorldItem[]> {
  const res = await authRequest<WorldsListResponse>(BASE);
  return res.items;
}

export async function getWorld(id: string): Promise<WorldDetail> {
  return authRequest<WorldDetail>(`${BASE}/${id}`);
}

export async function createWorld(data: CreateWorldRequest): Promise<WorldItem> {
  return authRequest<WorldItem>(BASE, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateWorld(id: string, data: UpdateWorldRequest): Promise<WorldItem> {
  return authRequest<WorldItem>(`${BASE}/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function cloneWorld(id: string): Promise<WorldItem> {
  return authRequest<WorldItem>(`${BASE}/${id}/clone`, {
    method: "POST",
  });
}

export async function deleteWorld(id: string): Promise<void> {
  return authRequest<void>(`${BASE}/${id}`, {
    method: "DELETE",
  });
}

export interface ReindexWorldResult {
  indexed_count: number;
  warning: string | null;
}

export async function reindexWorld(worldId: string): Promise<ReindexWorldResult> {
  return authRequest<ReindexWorldResult>(`${BASE}/${worldId}/reindex`, {
    method: "POST",
  });
}

// ── Documents ───────────────────────────────────────────────────

export async function listDocuments(worldId: string, docType?: string): Promise<DocumentItem[]> {
  const params = docType ? `?doc_type=${docType}` : "";
  const res = await authRequest<DocumentsListResponse>(`${BASE}/${worldId}/documents${params}`);
  return res.items;
}

export async function getDocument(worldId: string, docId: string): Promise<DocumentItem> {
  return authRequest<DocumentItem>(`${BASE}/${worldId}/documents/${docId}`);
}

export async function createDocument(worldId: string, data: CreateDocumentRequest): Promise<DocumentSaveResponse> {
  return authRequest<DocumentSaveResponse>(`${BASE}/${worldId}/documents`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateDocument(
  worldId: string, docId: string, data: UpdateDocumentRequest,
): Promise<DocumentSaveResponse> {
  return authRequest<DocumentSaveResponse>(`${BASE}/${worldId}/documents/${docId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteDocument(worldId: string, docId: string): Promise<void> {
  return authRequest<void>(`${BASE}/${worldId}/documents/${docId}`, {
    method: "DELETE",
  });
}

export async function uploadDocuments(worldId: string, files: File[], docType: string): Promise<DocumentSaveResponse[]> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  const token = getToken();
  const res = await fetch(`${BASE}/${worldId}/documents/upload?doc_type=${docType}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || res.statusText);
  }
  return res.json() as Promise<DocumentSaveResponse[]>;
}

export async function downloadDocument(worldId: string, docId: string): Promise<void> {
  const token = getToken();
  const res = await fetch(`${BASE}/${worldId}/documents/${docId}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("Download failed");
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

export async function downloadAllDocuments(worldId: string): Promise<void> {
  const token = getToken();
  const res = await fetch(`${BASE}/${worldId}/documents/download-all`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("Download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `world_${worldId}_documents.zip`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Stats ───────────────────────────────────────────────────────

export async function listStats(worldId: string): Promise<StatDefinitionItem[]> {
  return authRequest<StatDefinitionItem[]>(`${BASE}/${worldId}/stats`);
}

export async function createStat(worldId: string, data: CreateStatRequest): Promise<StatDefinitionItem> {
  return authRequest<StatDefinitionItem>(`${BASE}/${worldId}/stats`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateStat(
  worldId: string, statId: string, data: UpdateStatRequest,
): Promise<StatDefinitionItem> {
  return authRequest<StatDefinitionItem>(`${BASE}/${worldId}/stats/${statId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteStat(worldId: string, statId: string): Promise<void> {
  return authRequest<void>(`${BASE}/${worldId}/stats/${statId}`, {
    method: "DELETE",
  });
}

// ── Rules ───────────────────────────────────────────────────────

export async function listRules(worldId: string): Promise<RuleItem[]> {
  return authRequest<RuleItem[]>(`${BASE}/${worldId}/rules`);
}

export async function createRule(worldId: string, data: CreateRuleRequest): Promise<RuleItem> {
  return authRequest<RuleItem>(`${BASE}/${worldId}/rules`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateRule(
  worldId: string, ruleId: string, data: UpdateRuleRequest,
): Promise<RuleItem> {
  return authRequest<RuleItem>(`${BASE}/${worldId}/rules/${ruleId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteRule(worldId: string, ruleId: string): Promise<void> {
  return authRequest<void>(`${BASE}/${worldId}/rules/${ruleId}`, {
    method: "DELETE",
  });
}

export async function reorderRules(worldId: string, ruleIds: string[]): Promise<RuleItem[]> {
  return authRequest<RuleItem[]>(`${BASE}/${worldId}/rules/reorder`, {
    method: "PUT",
    body: JSON.stringify({ rule_ids: ruleIds }),
  });
}

// ── NPC-Location Links ──────────────────────────────────────────

export async function listLinks(worldId: string): Promise<NpcLocationLinkItem[]> {
  const res = await authRequest<NpcLocationLinksListResponse>(`${BASE}/${worldId}/npc-location-links`);
  return res.items;
}

export async function createLink(worldId: string, data: CreateNpcLocationLinkRequest): Promise<NpcLocationLinkItem> {
  return authRequest<NpcLocationLinkItem>(`${BASE}/${worldId}/npc-location-links`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteLink(worldId: string, linkId: string): Promise<void> {
  return authRequest<void>(`${BASE}/${worldId}/npc-location-links/${linkId}`, {
    method: "DELETE",
  });
}
