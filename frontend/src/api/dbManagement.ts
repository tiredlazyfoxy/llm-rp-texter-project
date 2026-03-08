import { getToken } from "../auth";
import { authRequest } from "./request";
import type { DbStatusResponse, TableStatus } from "../types/dbManagement";

const BASE = "/api/admin/db";

export async function getDbStatus(): Promise<TableStatus[]> {
  const res = await authRequest<DbStatusResponse>(BASE);
  return res.tables;
}

export async function createTable(tableName: string): Promise<void> {
  await authRequest<void>(`${BASE}/tables/${tableName}/create`, {
    method: "POST",
  });
}

export async function exportDb(): Promise<void> {
  const token = getToken();
  const res = await fetch(`${BASE}/export`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || res.statusText);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "llmrp_export.zip";
  a.click();
  URL.revokeObjectURL(url);
}

export async function importDb(file: File): Promise<void> {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/import`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || res.statusText);
  }
}
