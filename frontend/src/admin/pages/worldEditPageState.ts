import { makeAutoObservable, runInAction } from "mobx";
import { ApiError } from "../../api/client";
import type {
  RuleItem,
  StatDefinitionItem,
  UpdateWorldRequest,
  WorldDetail,
} from "../../types/world";
import type { PipelineItem } from "../../types/pipeline";
import {
  cloneWorld as apiCloneWorld,
  deleteWorld as apiDeleteWorld,
  getWorld,
  reorderRules as apiReorderRules,
  updateWorld,
} from "../../api/worlds";
import { listPipelines } from "../../api/pipelines";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

export interface WorldDraft {
  name: string;
  description: string;
  lore: string;
  character_template: string;
  initial_message: string;
  pipeline_id: string | null;
  status: string;
}

export type WorldDraftErrors = Partial<Record<keyof WorldDraft, string>>;

function emptyDraft(): WorldDraft {
  return {
    name: "",
    description: "",
    lore: "",
    character_template: "",
    initial_message: "",
    pipeline_id: null,
    status: "draft",
  };
}

function draftFromWorld(world: WorldDetail): WorldDraft {
  return {
    name: world.name,
    description: world.description,
    lore: world.lore,
    character_template: world.character_template,
    initial_message: world.initial_message,
    pipeline_id: world.pipeline_id,
    status: world.status,
  };
}

function draftEqualsWorld(draft: WorldDraft, world: WorldDetail): boolean {
  return (
    draft.name === world.name &&
    draft.description === world.description &&
    draft.lore === world.lore &&
    draft.character_template === world.character_template &&
    draft.initial_message === world.initial_message &&
    draft.pipeline_id === world.pipeline_id &&
    draft.status === world.status
  );
}

/**
 * Page state for `WorldEditPage` (`/admin/worlds/:worldId/edit`).
 */
export class WorldEditPageState {
  worldId: string;

  world: WorldDetail | null = null;
  worldStatus: AsyncStatus = "idle";
  worldError: string | null = null;

  pipelines: PipelineItem[] = [];
  pipelinesStatus: AsyncStatus = "idle";
  pipelinesError: string | null = null;

  draft: WorldDraft = emptyDraft();
  serverErrors: WorldDraftErrors = {};

  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;
  saveSuccess: string | null = null;

  cloneStatus: AsyncStatus = "idle";
  deleteStatus: AsyncStatus = "idle";

  // Stats / rules sub-state
  stats: StatDefinitionItem[] = [];
  rules: RuleItem[] = [];

  constructor(worldId: string) {
    this.worldId = worldId;
    makeAutoObservable(this);
  }

  get errors(): WorldDraftErrors {
    const e: WorldDraftErrors = {};
    if (!this.draft.name.trim()) e.name = "Name is required";
    return { ...e, ...this.serverErrors };
  }

  get isValid(): boolean {
    return Object.keys(this.errors).length === 0;
  }

  get isDirty(): boolean {
    if (!this.world) return false;
    return !draftEqualsWorld(this.draft, this.world);
  }

  get canSubmit(): boolean {
    return this.isValid && this.isDirty && this.saveStatus !== "loading";
  }
}

export async function loadWorldEdit(state: WorldEditPageState, signal: AbortSignal): Promise<void> {
  state.worldStatus = "loading";
  state.worldError = null;
  state.pipelinesStatus = "loading";
  state.pipelinesError = null;
  try {
    const [world, pipelines] = await Promise.all([
      getWorld(state.worldId, signal),
      listPipelines(signal).catch((err: unknown) => {
        // Pipelines failure shouldn't block the main load.
        runInAction(() => {
          state.pipelinesStatus = "error";
          state.pipelinesError = err instanceof Error ? err.message : String(err);
        });
        return [] as PipelineItem[];
      }),
    ]);
    if (signal.aborted) return;
    runInAction(() => {
      state.world = world;
      state.draft = draftFromWorld(world);
      state.stats = world.stats;
      state.rules = world.rules;
      state.serverErrors = {};
      state.worldStatus = "ready";
      if (state.pipelinesStatus !== "error") {
        state.pipelines = pipelines;
        state.pipelinesStatus = "ready";
      }
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.worldStatus = "error";
      state.worldError = err instanceof Error ? err.message : String(err);
    });
  }
}

/** Reload stats + rules after a modal CRUD completes. */
export async function refreshStatsAndRules(
  state: WorldEditPageState,
  signal: AbortSignal,
): Promise<void> {
  try {
    const world = await getWorld(state.worldId, signal);
    runInAction(() => {
      state.world = world;
      state.stats = world.stats;
      state.rules = world.rules;
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.saveError = err instanceof Error ? err.message : String(err);
    });
  }
}

export async function saveWorld(state: WorldEditPageState, signal: AbortSignal): Promise<void> {
  if (!state.canSubmit) return;
  state.saveStatus = "loading";
  state.saveError = null;
  state.saveSuccess = null;
  try {
    const req: UpdateWorldRequest = {
      name: state.draft.name,
      description: state.draft.description,
      lore: state.draft.lore,
      character_template: state.draft.character_template,
      initial_message: state.draft.initial_message,
      pipeline_id: state.draft.pipeline_id,
      status: state.draft.status,
    };
    await updateWorld(state.worldId, req, signal);
    // Refetch to keep both world snapshot and draft in sync with backend.
    const refreshed = await getWorld(state.worldId, signal);
    runInAction(() => {
      state.world = refreshed;
      state.draft = draftFromWorld(refreshed);
      state.stats = refreshed.stats;
      state.rules = refreshed.rules;
      state.serverErrors = {};
      state.saveStatus = "ready";
      state.saveSuccess = "World saved";
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

function mapServerErrors(details: unknown): WorldDraftErrors {
  const out: WorldDraftErrors = {};
  if (details && typeof details === "object" && "detail" in details) {
    const detail = (details as { detail: unknown }).detail;
    if (Array.isArray(detail)) {
      for (const entry of detail) {
        if (entry && typeof entry === "object" && "loc" in entry && "msg" in entry) {
          const loc = (entry as { loc: unknown[] }).loc;
          const msg = String((entry as { msg: unknown }).msg);
          const field = loc[loc.length - 1];
          if (typeof field === "string" && field in ({ name: 1, description: 1, lore: 1, character_template: 1, initial_message: 1, pipeline_id: 1, status: 1 } as Record<string, number>)) {
            out[field as keyof WorldDraft] = msg;
          }
        }
      }
    }
  }
  return out;
}

export async function cloneWorld(
  state: WorldEditPageState,
  signal: AbortSignal,
): Promise<string | null> {
  state.cloneStatus = "loading";
  try {
    const cloned = await apiCloneWorld(state.worldId, signal);
    runInAction(() => {
      state.cloneStatus = "ready";
    });
    return cloned.id;
  } catch (err) {
    if (signal.aborted) return null;
    runInAction(() => {
      state.cloneStatus = "error";
      state.saveError = err instanceof Error ? err.message : String(err);
    });
    return null;
  }
}

export async function deleteWorld(
  state: WorldEditPageState,
  signal: AbortSignal,
): Promise<boolean> {
  state.deleteStatus = "loading";
  try {
    await apiDeleteWorld(state.worldId, signal);
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

export async function reorderRules(
  state: WorldEditPageState,
  ruleIds: string[],
  signal: AbortSignal,
): Promise<void> {
  try {
    const updated = await apiReorderRules(state.worldId, ruleIds, signal);
    runInAction(() => {
      state.rules = updated;
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.saveError = err instanceof Error ? err.message : String(err);
    });
  }
}
