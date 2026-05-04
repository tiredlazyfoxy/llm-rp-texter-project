import { makeAutoObservable, runInAction } from "mobx";
import type { CreateWorldRequest, WorldItem } from "../../types/world";
import { createWorld, listWorlds } from "../../api/worlds";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

/**
 * Page state for `WorldsListPage` (`/admin/worlds`).
 *
 * Holds the worlds list trio. The create-world modal owns its own
 * draft (component-local class), per `frontend-forms.md`.
 */
export class WorldsListPageState {
  worlds: WorldItem[] = [];
  worldsStatus: AsyncStatus = "idle";
  worldsError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

export async function loadWorlds(state: WorldsListPageState, signal: AbortSignal): Promise<void> {
  state.worldsStatus = "loading";
  state.worldsError = null;
  try {
    const worlds = await listWorlds(signal);
    runInAction(() => {
      state.worlds = worlds;
      state.worldsStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.worldsStatus = "error";
      state.worldsError = err instanceof Error ? err.message : String(err);
    });
  }
}

// ── Create-world modal draft ────────────────────────────────────

interface CreateWorldDraftErrors {
  name?: string;
}

/**
 * Component-local draft for the create-world modal.
 * Held in `WorldsListPage` via `useState(() => new CreateWorldDraft())`.
 */
export class CreateWorldDraft {
  name = "";
  description = "";
  status = "draft";

  serverErrors: CreateWorldDraftErrors = {};
  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  reset(): void {
    this.name = "";
    this.description = "";
    this.status = "draft";
    this.serverErrors = {};
    this.saveStatus = "idle";
    this.saveError = null;
  }

  get errors(): CreateWorldDraftErrors {
    const e: CreateWorldDraftErrors = {};
    if (!this.name.trim()) e.name = "Name is required";
    return { ...e, ...this.serverErrors };
  }

  get isValid(): boolean {
    return Object.keys(this.errors).length === 0;
  }

  get canSubmit(): boolean {
    return this.isValid && this.saveStatus !== "loading";
  }
}

export async function createNewWorld(
  draft: CreateWorldDraft,
  signal: AbortSignal,
): Promise<WorldItem | null> {
  if (!draft.canSubmit) return null;
  draft.saveStatus = "loading";
  draft.saveError = null;
  try {
    const req: CreateWorldRequest = {
      name: draft.name.trim(),
      description: draft.description,
      status: draft.status,
    };
    const created = await createWorld(req, signal);
    runInAction(() => {
      draft.saveStatus = "ready";
    });
    return created;
  } catch (err) {
    if (signal.aborted) return null;
    runInAction(() => {
      draft.saveStatus = "error";
      draft.saveError = err instanceof Error ? err.message : String(err);
    });
    return null;
  }
}
