import { makeAutoObservable, runInAction } from "mobx";
import type { LlmServerItem } from "../../types/llmServer";
import {
  clearEmbedding as apiClearEmbedding,
  deleteServer as apiDeleteServer,
  listServers,
} from "../../api/llmServers";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

/**
 * Page state for `LlmServersPage` (`/admin/llm-servers`).
 *
 * Holds the servers trio. The four edit/create/models/embedding modals
 * own their own draft classes (component-local) per
 * `frontend-forms.md`; the page only tracks which target is active.
 * Modal target flags are kept as plain `useState` in the page since
 * they're transient UI flags (see `frontend-state.md` line 41).
 */
export class LlmServersPageState {
  servers: LlmServerItem[] = [];
  serversStatus: AsyncStatus = "idle";
  serversError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

export async function loadServers(
  state: LlmServersPageState,
  signal: AbortSignal,
): Promise<void> {
  state.serversStatus = "loading";
  state.serversError = null;
  try {
    const servers = await listServers(signal);
    runInAction(() => {
      state.servers = servers;
      state.serversStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.serversStatus = "error";
      state.serversError = err instanceof Error ? err.message : String(err);
    });
  }
}

export function clearServersError(state: LlmServersPageState): void {
  state.serversError = null;
}

/** Confirm + delete a server, then refresh the list. */
export async function deleteServerAction(
  state: LlmServersPageState,
  server: LlmServerItem,
  signal: AbortSignal,
): Promise<boolean> {
  if (!window.confirm(`Delete server "${server.name}"? This cannot be undone.`)) {
    return false;
  }
  try {
    await apiDeleteServer(server.id, signal);
    await loadServers(state, signal);
    return true;
  } catch (err) {
    if (signal.aborted) return false;
    runInAction(() => {
      state.serversError = err instanceof Error ? err.message : "Failed to delete server";
    });
    return false;
  }
}

/** Confirm + clear cluster-wide embedding designation, then refresh. */
export async function clearEmbeddingAction(
  state: LlmServersPageState,
  server: LlmServerItem,
  signal: AbortSignal,
): Promise<boolean> {
  if (!window.confirm(`Remove embedding designation from "${server.name}"?`)) {
    return false;
  }
  try {
    await apiClearEmbedding(signal);
    await loadServers(state, signal);
    return true;
  } catch (err) {
    if (signal.aborted) return false;
    runInAction(() => {
      state.serversError = err instanceof Error ? err.message : "Failed to clear embedding";
    });
    return false;
  }
}
