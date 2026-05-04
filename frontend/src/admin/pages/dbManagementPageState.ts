import { makeAutoObservable, runInAction } from "mobx";
import type { TableStatus } from "../../types/dbManagement";
import {
  createTable,
  exportDb,
  getDbStatus,
  importDb,
  reindexVectors,
  syncTable,
} from "../../api/dbManagement";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

/**
 * Page state for `DbManagementPage` (`/admin/database`).
 *
 * Holds the tables trio plus a generic admin-action trio that covers
 * create-table / sync / reindex / export / import — only one such
 * action runs at a time. Per-row "which table is being acted on"
 * is captured via `actionLabel`.
 *
 * The schema-detail modal target is component-local UI state on the
 * page (plain `useState`), see `frontend-state.md` line 41.
 */
export class DbManagementPageState {
  tables: TableStatus[] = [];
  tablesStatus: AsyncStatus = "idle";
  tablesError: string | null = null;

  actionStatus: AsyncStatus = "idle";
  actionError: string | null = null;
  /**
   * Identifies the in-flight admin action so the UI can render a
   * spinner on the right button. Format:
   *   "export" | "import" | "reindex"
   *   | "create:<table_name>" | "sync:<table_name>"
   * `null` when no action is running.
   */
  actionLabel: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

export async function loadDbStatus(
  state: DbManagementPageState,
  signal: AbortSignal,
): Promise<void> {
  state.tablesStatus = "loading";
  state.tablesError = null;
  try {
    const tables = await getDbStatus(signal);
    runInAction(() => {
      state.tables = tables;
      state.tablesStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.tablesStatus = "error";
      state.tablesError = err instanceof Error ? err.message : String(err);
    });
  }
}

export function clearActionError(state: DbManagementPageState): void {
  state.actionError = null;
}

export function clearTablesError(state: DbManagementPageState): void {
  state.tablesError = null;
}

function startAction(state: DbManagementPageState, label: string): void {
  state.actionStatus = "loading";
  state.actionError = null;
  state.actionLabel = label;
}

function endAction(state: DbManagementPageState, status: AsyncStatus, error: string | null): void {
  state.actionStatus = status;
  state.actionError = error;
  state.actionLabel = null;
}

export async function createTableAction(
  state: DbManagementPageState,
  tableName: string,
  signal: AbortSignal,
): Promise<void> {
  startAction(state, `create:${tableName}`);
  try {
    await createTable(tableName, signal);
    await loadDbStatus(state, signal);
    runInAction(() => endAction(state, "ready", null));
  } catch (err) {
    if (signal.aborted) return;
    const msg = err instanceof Error ? err.message : "Failed to create table";
    runInAction(() => endAction(state, "error", msg));
  }
}

export async function syncTableAction(
  state: DbManagementPageState,
  tableName: string,
  signal: AbortSignal,
): Promise<boolean> {
  startAction(state, `sync:${tableName}`);
  try {
    await syncTable(tableName, signal);
    await loadDbStatus(state, signal);
    runInAction(() => endAction(state, "ready", null));
    return true;
  } catch (err) {
    if (signal.aborted) return false;
    const msg = err instanceof Error ? err.message : "Sync failed";
    runInAction(() => endAction(state, "error", msg));
    return false;
  }
}

export async function reindexVectorsAction(
  state: DbManagementPageState,
  signal: AbortSignal,
): Promise<void> {
  if (!window.confirm("Rebuild vector index for all world documents? This may take a while.")) {
    return;
  }
  startAction(state, "reindex");
  try {
    const result = await reindexVectors(signal);
    if (!result.success) {
      runInAction(() => endAction(state, "error", result.error ?? "Reindex failed"));
      return;
    }
    runInAction(() => endAction(state, "ready", null));
  } catch (err) {
    if (signal.aborted) return;
    const msg = err instanceof Error ? err.message : "Reindex failed";
    runInAction(() => endAction(state, "error", msg));
  }
}

export async function exportDbAction(
  state: DbManagementPageState,
  signal: AbortSignal,
): Promise<void> {
  startAction(state, "export");
  try {
    await exportDb(signal);
    runInAction(() => endAction(state, "ready", null));
  } catch (err) {
    if (signal.aborted) return;
    const msg = err instanceof Error ? err.message : "Export failed";
    runInAction(() => endAction(state, "error", msg));
  }
}

export async function importDbAction(
  state: DbManagementPageState,
  file: File,
  signal: AbortSignal,
): Promise<void> {
  if (!window.confirm("Import will overwrite existing data. Continue?")) return;
  startAction(state, "import");
  try {
    await importDb(file, signal);
    await loadDbStatus(state, signal);
    runInAction(() => endAction(state, "ready", null));
  } catch (err) {
    if (signal.aborted) return;
    const msg = err instanceof Error ? err.message : "Import failed";
    runInAction(() => endAction(state, "error", msg));
  }
}
