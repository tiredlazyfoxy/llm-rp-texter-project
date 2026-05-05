import { makeAutoObservable, runInAction } from "mobx";
import type { DocumentItem, WorldDetail } from "../../types/world";
import {
  deleteDocument as apiDeleteDocument,
  downloadAllDocuments as apiDownloadAllDocuments,
  downloadDocument as apiDownloadDocument,
  getWorld,
  listDocuments,
  reindexWorld as apiReindexWorld,
  uploadDocuments as apiUploadDocuments,
} from "../../api/worlds";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

export type WorldViewTab = "info" | "all" | "location" | "npc" | "lore_fact" | "chats";

export const VALID_TABS: WorldViewTab[] = ["info", "all", "location", "npc", "lore_fact", "chats"];

/**
 * Page state for `WorldViewPage` (`/admin/worlds/:worldId`).
 *
 * One world detail trio plus a per-active-tab documents trio.
 * Tab is mirrored to the `?tab=...` query param. The original page
 * polled the world detail every 30 s; this state matches that behavior
 * via `pollWorld(state, signal)` started by the page's mount effect.
 */
export class WorldViewPageState {
  worldId: string;

  world: WorldDetail | null = null;
  worldStatus: AsyncStatus = "idle";
  worldError: string | null = null;

  tab: WorldViewTab = "info";

  docs: DocumentItem[] = [];
  docsStatus: AsyncStatus = "idle";
  docsError: string | null = null;

  reindexStatus: AsyncStatus = "idle";
  reindexError: string | null = null;

  createDocStatus: AsyncStatus = "idle";

  constructor(worldId: string, initialTab: WorldViewTab = "info") {
    this.worldId = worldId;
    this.tab = initialTab;
    makeAutoObservable(this);
  }

  /** Returns the doc-type filter for the current tab, or undefined for "all". */
  get docTypeFilter(): string | undefined {
    if (this.tab === "info" || this.tab === "chats" || this.tab === "all") return undefined;
    return this.tab;
  }

  /** Whether the current tab is a documents tab (loads docs). */
  get isDocsTab(): boolean {
    return this.tab === "all" || this.tab === "location" || this.tab === "npc" || this.tab === "lore_fact";
  }
}

export async function loadWorld(state: WorldViewPageState, signal: AbortSignal): Promise<void> {
  state.worldStatus = "loading";
  state.worldError = null;
  try {
    const world = await getWorld(state.worldId, signal);
    runInAction(() => {
      state.world = world;
      state.worldStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.worldStatus = "error";
      state.worldError = err instanceof Error ? err.message : String(err);
    });
  }
}

/** Background world refresh — does not flip the loading status. */
export async function refreshWorld(state: WorldViewPageState, signal: AbortSignal): Promise<void> {
  try {
    const world = await getWorld(state.worldId, signal);
    runInAction(() => {
      state.world = world;
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.worldError = err instanceof Error ? err.message : String(err);
    });
  }
}

export async function loadDocs(state: WorldViewPageState, signal: AbortSignal): Promise<void> {
  if (!state.isDocsTab) {
    runInAction(() => {
      state.docs = [];
      state.docsStatus = "ready";
    });
    return;
  }
  state.docsStatus = "loading";
  state.docsError = null;
  try {
    const docs = await listDocuments(state.worldId, state.docTypeFilter, signal);
    runInAction(() => {
      state.docs = docs;
      state.docsStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.docsStatus = "error";
      state.docsError = err instanceof Error ? err.message : String(err);
    });
  }
}

/** Background docs refresh — does not flip the loading status. */
export async function refreshDocs(state: WorldViewPageState, signal: AbortSignal): Promise<void> {
  if (!state.isDocsTab) return;
  try {
    const docs = await listDocuments(state.worldId, state.docTypeFilter, signal);
    runInAction(() => {
      state.docs = docs;
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.docsError = err instanceof Error ? err.message : String(err);
    });
  }
}

export async function deleteDocument(
  state: WorldViewPageState,
  doc: DocumentItem,
  signal: AbortSignal,
): Promise<void> {
  try {
    await apiDeleteDocument(state.worldId, doc.id, signal);
    await refreshDocs(state, signal);
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.docsError = err instanceof Error ? err.message : String(err);
    });
  }
}

export async function downloadDocument(
  state: WorldViewPageState,
  doc: DocumentItem,
  signal: AbortSignal,
): Promise<void> {
  try {
    await apiDownloadDocument(state.worldId, doc.id, signal);
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.docsError = err instanceof Error ? err.message : String(err);
    });
  }
}

export async function downloadAllDocuments(
  state: WorldViewPageState,
  signal: AbortSignal,
): Promise<void> {
  try {
    await apiDownloadAllDocuments(state.worldId, signal);
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.docsError = err instanceof Error ? err.message : String(err);
    });
  }
}

export async function uploadDocuments(
  state: WorldViewPageState,
  files: File[],
  docType: string,
  signal: AbortSignal,
): Promise<void> {
  try {
    await apiUploadDocuments(state.worldId, files, docType, signal);
    await refreshDocs(state, signal);
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.docsError = err instanceof Error ? err.message : String(err);
    });
  }
}

export async function reindexWorld(
  state: WorldViewPageState,
  signal: AbortSignal,
): Promise<{ indexed_count: number; warning: string | null } | null> {
  state.reindexStatus = "loading";
  state.reindexError = null;
  try {
    const result = await apiReindexWorld(state.worldId, signal);
    runInAction(() => {
      state.reindexStatus = "ready";
      if (result.warning) state.reindexError = result.warning;
    });
    return result;
  } catch (err) {
    if (signal.aborted) return null;
    runInAction(() => {
      state.reindexStatus = "error";
      state.reindexError = err instanceof Error ? err.message : String(err);
    });
    return null;
  }
}

