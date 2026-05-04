import { getToken } from "../auth";
import { request, throwApiError } from "./client";
import type { DbStatusResponse, ReindexResult, SyncResult, TableStatus } from "../types/dbManagement";

const BASE = "/api/admin/db";

export async function getDbStatus(signal?: AbortSignal): Promise<TableStatus[]> {
  const res = await request<DbStatusResponse>(BASE, { signal });
  return res.tables;
}

export async function createTable(tableName: string, signal?: AbortSignal): Promise<void> {
  await request<void>(`${BASE}/tables/${tableName}/create`, {
    method: "POST",
    signal,
  });
}

export async function syncTable(tableName: string, signal?: AbortSignal): Promise<SyncResult> {
  return request<SyncResult>(`${BASE}/tables/${tableName}/sync`, {
    method: "POST",
    signal,
  });
}

export async function exportDb(signal?: AbortSignal): Promise<void> {
  const token = getToken();
  const res = await fetch(`${BASE}/export`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  });
  if (!res.ok) await throwApiError(res);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "llmrp_export.zip";
  a.click();
  URL.revokeObjectURL(url);
}

export async function reindexVectors(signal?: AbortSignal): Promise<ReindexResult> {
  return request<ReindexResult>(`${BASE}/reindex-vectors`, {
    method: "POST",
    signal,
  });
}

export async function importDb(file: File, signal?: AbortSignal): Promise<void> {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/import`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
    signal,
  });
  if (!res.ok) await throwApiError(res);
}
