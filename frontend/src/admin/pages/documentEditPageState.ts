import { makeAutoObservable, runInAction } from "mobx";
import { ApiError } from "../../api/client";
import type { DocumentItem } from "../../types/world";
import {
  createDocument,
  createLink,
  deleteDocument as apiDeleteDocument,
  deleteLink,
  getDocument,
  listDocuments,
  updateDocument,
} from "../../api/worlds";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

export interface DocumentDraft {
  name: string;
  content: string;
  exits: string[];
  isInjected: boolean;
  weight: number;
  allowedIds: string[];
  prohibitedIds: string[];
}

/**
 * Queued link create/delete intent captured while the document is still a
 * draft (`isNew === true`). Replayed against the link API after the
 * document itself is persisted.
 */
export type LinkOp =
  | { kind: "create"; linkType: string; otherId: string }
  | { kind: "delete"; linkType: string; otherId: string };

export type DocumentDraftErrors = Partial<Record<keyof DocumentDraft, string>>;

const DRAFT_FIELD_KEYS: Record<keyof DocumentDraft, true> = {
  name: true,
  content: true,
  exits: true,
  isInjected: true,
  weight: true,
  allowedIds: true,
  prohibitedIds: true,
};

/**
 * Page state for `DocumentEditPage` (`/admin/worlds/:worldId/documents/:docId/edit`).
 *
 * `LlmChatPanel` is treated as a black box; its `onApply` / `onAppend`
 * callbacks mutate `state.draft.content`.
 */
export class DocumentEditPageState {
  worldId: string;
  docId: string;

  /**
   * True when the page was opened via `?new=1`, meaning the document does
   * not yet exist on the server. Flips to `false` after the first
   * successful Save.
   */
  isNew: boolean;
  initialDocType: string | null;

  doc: DocumentItem | null = null;
  loadStatus: AsyncStatus = "idle";
  loadError: string | null = null;

  draft: DocumentDraft = {
    name: "",
    content: "",
    exits: [],
    isInjected: false,
    weight: 0,
    allowedIds: [],
    prohibitedIds: [],
  };

  serverErrors: DocumentDraftErrors = {};

  originalContent = "";
  originalIsInjected = false;
  originalWeight = 0;

  // Options for related-document multi-selects
  locationOptions: { value: string; label: string }[] = [];
  linkOptions: { value: string; label: string }[] = [];

  /** Link create/delete intents queued while `isNew` is true. */
  pendingLinkOps: LinkOp[] = [];

  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;
  saveSuccess: string | null = null;
  embeddingWarning: string | null = null;

  deleteStatus: AsyncStatus = "idle";

  constructor(
    worldId: string,
    docId: string,
    options?: { isNew?: boolean; initialDocType?: string | null },
  ) {
    this.worldId = worldId;
    this.docId = docId;
    this.isNew = options?.isNew ?? false;
    this.initialDocType = options?.initialDocType ?? null;
    makeAutoObservable(this);
  }

  get errors(): DocumentDraftErrors {
    const e: DocumentDraftErrors = {};
    if (this.doc && this.doc.doc_type !== "lore_fact" && !this.draft.name.trim()) {
      e.name = "Name is required";
    }
    return { ...e, ...this.serverErrors };
  }

  get isValid(): boolean {
    return Object.keys(this.errors).length === 0;
  }

  get isDirty(): boolean {
    if (this.isNew) return true;
    if (!this.doc) return false;
    if (this.draft.content !== this.originalContent) return true;
    if (this.doc.doc_type === "lore_fact") {
      if (this.draft.isInjected !== this.originalIsInjected) return true;
      if (this.draft.weight !== this.originalWeight) return true;
    }
    return false;
  }

  get canSubmit(): boolean {
    return this.isValid && this.saveStatus !== "loading";
  }
}

function emptyDraftDoc(
  worldId: string,
  docId: string,
  docType: string,
): DocumentItem {
  return {
    id: docId,
    doc_type: docType,
    world_id: worldId,
    name: docType === "lore_fact" ? null : "",
    content: "",
    created_at: null,
    modified_at: null,
    exits: docType === "location" ? [] : null,
    links: docType === "npc" ? [] : null,
    linked_npcs: docType === "location" ? [] : null,
    is_injected: false,
    weight: 0,
  };
}

async function loadDraftDocument(
  state: DocumentEditPageState,
  signal: AbortSignal,
): Promise<void> {
  state.loadStatus = "loading";
  state.loadError = null;
  const docType = state.initialDocType ?? "location";
  try {
    let locationOptions: { value: string; label: string }[] = [];
    let linkOptions: { value: string; label: string }[] = [];

    if (docType === "npc") {
      const locs = await listDocuments(state.worldId, "location", signal);
      linkOptions = locs.map(l => ({ value: l.id, label: l.name || "(untitled)" }));
    } else if (docType === "location") {
      const [locs, npcs] = await Promise.all([
        listDocuments(state.worldId, "location", signal),
        listDocuments(state.worldId, "npc", signal),
      ]);
      locationOptions = locs
        .filter(l => l.id !== state.docId)
        .map(l => ({ value: l.id, label: l.name || "(untitled)" }));
      linkOptions = npcs.map(n => ({ value: n.id, label: n.name || "(untitled)" }));
    }

    if (signal.aborted) return;
    runInAction(() => {
      state.doc = emptyDraftDoc(state.worldId, state.docId, docType);
      state.draft = {
        name: "",
        content: "",
        exits: [],
        isInjected: false,
        weight: 0,
        allowedIds: [],
        prohibitedIds: [],
      };
      state.originalContent = "";
      state.originalIsInjected = false;
      state.originalWeight = 0;
      state.locationOptions = locationOptions;
      state.linkOptions = linkOptions;
      state.pendingLinkOps = [];
      state.serverErrors = {};
      state.loadStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.loadStatus = "error";
      state.loadError = err instanceof Error ? err.message : String(err);
    });
  }
}

export async function loadDocument(state: DocumentEditPageState, signal: AbortSignal): Promise<void> {
  if (state.isNew) {
    await loadDraftDocument(state, signal);
    return;
  }
  state.loadStatus = "loading";
  state.loadError = null;
  try {
    const doc = await getDocument(state.worldId, state.docId, signal);
    let locationOptions: { value: string; label: string }[] = [];
    let linkOptions: { value: string; label: string }[] = [];
    let allowedIds: string[] = [];
    let prohibitedIds: string[] = [];

    if (doc.doc_type === "npc") {
      const locs = await listDocuments(state.worldId, "location", signal);
      linkOptions = locs.map(l => ({ value: l.id, label: l.name || "(untitled)" }));
      const links = doc.links || [];
      allowedIds = links.filter(l => l.link_type === "present").map(l => l.location_id);
      prohibitedIds = links.filter(l => l.link_type === "excluded").map(l => l.location_id);
    } else if (doc.doc_type === "location") {
      const [locs, npcs] = await Promise.all([
        listDocuments(state.worldId, "location", signal),
        listDocuments(state.worldId, "npc", signal),
      ]);
      locationOptions = locs
        .filter(l => l.id !== state.docId)
        .map(l => ({ value: l.id, label: l.name || "(untitled)" }));
      linkOptions = npcs.map(n => ({ value: n.id, label: n.name || "(untitled)" }));
      const links = doc.linked_npcs || [];
      allowedIds = links.filter(l => l.link_type === "present").map(l => l.npc_id);
      prohibitedIds = links.filter(l => l.link_type === "excluded").map(l => l.npc_id);
    }

    if (signal.aborted) return;
    runInAction(() => {
      state.doc = doc;
      state.draft = {
        name: doc.name || "",
        content: doc.content,
        exits: doc.exits || [],
        isInjected: doc.is_injected,
        weight: doc.weight,
        allowedIds,
        prohibitedIds,
      };
      state.originalContent = doc.content;
      state.originalIsInjected = doc.is_injected;
      state.originalWeight = doc.weight;
      state.locationOptions = locationOptions;
      state.linkOptions = linkOptions;
      state.serverErrors = {};
      state.loadStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.loadStatus = "error";
      state.loadError = err instanceof Error ? err.message : String(err);
    });
  }
}

async function syncLinks(
  state: DocumentEditPageState,
  linkType: string,
  oldIds: string[],
  newIds: string[],
  signal: AbortSignal,
): Promise<void> {
  const doc = state.doc;
  if (!doc) return;
  const oldSet = new Set(oldIds);
  const newSet = new Set(newIds);
  const toCreate = newIds.filter(id => !oldSet.has(id));
  const toDelete = oldIds.filter(id => !newSet.has(id));

  for (const id of toDelete) {
    let linkId: string | undefined;
    if (doc.doc_type === "npc") {
      linkId = (doc.links || []).find(l => l.location_id === id && l.link_type === linkType)?.link_id;
    } else {
      linkId = (doc.linked_npcs || []).find(l => l.npc_id === id && l.link_type === linkType)?.link_id;
    }
    if (linkId) await deleteLink(state.worldId, linkId, signal);
  }

  for (const id of toCreate) {
    if (doc.doc_type === "npc") {
      await createLink(state.worldId, { npc_id: state.docId, location_id: id, link_type: linkType }, signal);
    } else {
      await createLink(state.worldId, { npc_id: id, location_id: state.docId, link_type: linkType }, signal);
    }
  }
}

export async function saveDocument(state: DocumentEditPageState, signal: AbortSignal): Promise<void> {
  const doc = state.doc;
  if (!doc) return;
  if (!state.canSubmit) return;
  state.saveStatus = "loading";
  state.saveError = null;
  state.saveSuccess = null;
  state.embeddingWarning = null;
  try {
    if (state.isNew) {
      const created = await createDocument(
        state.worldId,
        {
          id: state.docId,
          doc_type: doc.doc_type,
          name: doc.doc_type !== "lore_fact" ? state.draft.name : undefined,
          content: state.draft.content,
          exits: doc.doc_type === "location" ? state.draft.exits : undefined,
        },
        signal,
      );
      if (signal.aborted) return;

      // Capture queued link ops from the draft, then replay them against the
      // freshly-created document. Replay sequentially so abort behaves; a
      // failure surfaces via saveStatus without rolling back the document.
      const queued: LinkOp[] = [];
      if (doc.doc_type === "npc" || doc.doc_type === "location") {
        for (const id of state.draft.allowedIds) {
          queued.push({ kind: "create", linkType: "present", otherId: id });
        }
        for (const id of state.draft.prohibitedIds) {
          queued.push({ kind: "create", linkType: "excluded", otherId: id });
        }
      }
      runInAction(() => {
        state.pendingLinkOps = queued;
      });

      for (const op of queued) {
        if (signal.aborted) return;
        if (op.kind === "create") {
          if (doc.doc_type === "npc") {
            await createLink(
              state.worldId,
              { npc_id: state.docId, location_id: op.otherId, link_type: op.linkType },
              signal,
            );
          } else if (doc.doc_type === "location") {
            await createLink(
              state.worldId,
              { npc_id: op.otherId, location_id: state.docId, link_type: op.linkType },
              signal,
            );
          }
        }
        // No "delete" replays in the create flow — drafts have no prior links.
      }

      runInAction(() => {
        state.embeddingWarning = created.embedding_warning;
        state.serverErrors = {};
        state.pendingLinkOps = [];
        state.isNew = false;
      });

      // Reload from server so doc, link ids, and originals reflect persisted state.
      await loadDocument(state, signal);
      runInAction(() => {
        state.saveStatus = "ready";
        state.saveSuccess = "Document saved";
      });
      return;
    }

    const result = await updateDocument(
      state.worldId,
      state.docId,
      {
        name: doc.doc_type !== "lore_fact" ? state.draft.name : undefined,
        content: state.draft.content,
        exits: doc.doc_type === "location" ? state.draft.exits : undefined,
        is_injected: doc.doc_type === "lore_fact" ? state.draft.isInjected : undefined,
        weight: doc.doc_type === "lore_fact" ? state.draft.weight : undefined,
      },
      signal,
    );
    if (signal.aborted) return;

    if (doc.doc_type === "npc") {
      const currentAllowed = (doc.links || []).filter(l => l.link_type === "present").map(l => l.location_id);
      const currentProhibited = (doc.links || []).filter(l => l.link_type === "excluded").map(l => l.location_id);
      await syncLinks(state, "present", currentAllowed, state.draft.allowedIds, signal);
      await syncLinks(state, "excluded", currentProhibited, state.draft.prohibitedIds, signal);
    } else if (doc.doc_type === "location") {
      const currentAllowed = (doc.linked_npcs || []).filter(l => l.link_type === "present").map(l => l.npc_id);
      const currentProhibited = (doc.linked_npcs || []).filter(l => l.link_type === "excluded").map(l => l.npc_id);
      await syncLinks(state, "present", currentAllowed, state.draft.allowedIds, signal);
      await syncLinks(state, "excluded", currentProhibited, state.draft.prohibitedIds, signal);
    }

    runInAction(() => {
      state.embeddingWarning = result.embedding_warning;
      state.serverErrors = {};
    });

    // Reload to refresh link data
    await loadDocument(state, signal);
    runInAction(() => {
      state.saveStatus = "ready";
      state.saveSuccess = "Document saved";
    });
  } catch (err) {
    if (signal.aborted) return;
    if (err instanceof ApiError && err.status === 422) {
      runInAction(() => {
        state.serverErrors = mapServerErrors(err.details);
        state.saveStatus = "ready";
      });
    } else {
      runInAction(() => {
        state.saveStatus = "error";
        state.saveError = err instanceof Error ? err.message : String(err);
      });
    }
  }
}

function mapServerErrors(details: unknown): DocumentDraftErrors {
  const out: DocumentDraftErrors = {};
  if (details && typeof details === "object" && "detail" in details) {
    const detail = (details as { detail: unknown }).detail;
    if (Array.isArray(detail)) {
      for (const entry of detail) {
        if (entry && typeof entry === "object" && "loc" in entry && "msg" in entry) {
          const loc = (entry as { loc: unknown[] }).loc;
          const msg = String((entry as { msg: unknown }).msg);
          const field = loc[loc.length - 1];
          if (typeof field === "string" && field in DRAFT_FIELD_KEYS) {
            out[field as keyof DocumentDraft] = msg;
          }
        }
      }
    }
  }
  return out;
}

export async function deleteDocument(
  state: DocumentEditPageState,
  signal: AbortSignal,
): Promise<boolean> {
  state.deleteStatus = "loading";
  try {
    await apiDeleteDocument(state.worldId, state.docId, signal);
    runInAction(() => {
      state.deleteStatus = "ready";
    });
    return true;
  } catch (err) {
    if (signal.aborted) return false;
    runInAction(() => {
      state.deleteStatus = "error";
      state.saveError = err instanceof Error ? err.message : String(err);
    });
    return false;
  }
}
