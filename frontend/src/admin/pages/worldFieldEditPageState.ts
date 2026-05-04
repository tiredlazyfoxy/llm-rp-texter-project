import { makeAutoObservable, runInAction } from "mobx";
import type { UpdateWorldRequest, WorldDetail } from "../../types/world";
import { getWorld, updateWorld } from "../../api/worlds";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

export type WorldFieldName = "description" | "initial_message";

const FIELD_LABELS: Record<WorldFieldName, string> = {
  description: "Description",
  initial_message: "Initial Message",
};

function getFieldValue(world: WorldDetail, field: WorldFieldName): string {
  if (field === "description") return world.description ?? "";
  if (field === "initial_message") return world.initial_message ?? "";
  return "";
}

/**
 * Page state for `WorldFieldEditPage` (`/admin/worlds/:worldId/field/:fieldName`).
 *
 * AI-assisted single-field editor. The `LlmChatPanel` is treated as a
 * black box; its `onApply` / `onAppend` callbacks mutate `state.draft`.
 */
export class WorldFieldEditPageState {
  worldId: string;
  fieldName: WorldFieldName;

  world: WorldDetail | null = null;
  worldStatus: AsyncStatus = "idle";
  worldError: string | null = null;

  draft = "";
  originalContent = "";

  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;
  saveSuccess: string | null = null;

  constructor(worldId: string, fieldName: WorldFieldName) {
    this.worldId = worldId;
    this.fieldName = fieldName;
    makeAutoObservable(this);
  }

  get fieldLabel(): string {
    return FIELD_LABELS[this.fieldName];
  }

  get isDirty(): boolean {
    return this.draft !== this.originalContent;
  }

  get canSubmit(): boolean {
    return this.isDirty && this.saveStatus !== "loading";
  }
}

export async function loadField(state: WorldFieldEditPageState, signal: AbortSignal): Promise<void> {
  state.worldStatus = "loading";
  state.worldError = null;
  try {
    const world = await getWorld(state.worldId, signal);
    const value = getFieldValue(world, state.fieldName);
    runInAction(() => {
      state.world = world;
      state.draft = value;
      state.originalContent = value;
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

export async function saveField(state: WorldFieldEditPageState, signal: AbortSignal): Promise<void> {
  if (!state.canSubmit) return;
  state.saveStatus = "loading";
  state.saveError = null;
  state.saveSuccess = null;
  try {
    const patch: UpdateWorldRequest = { [state.fieldName]: state.draft };
    await updateWorld(state.worldId, patch, signal);
    runInAction(() => {
      state.originalContent = state.draft;
      state.saveStatus = "ready";
      state.saveSuccess = "Applied.";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.saveStatus = "error";
      state.saveError = err instanceof Error ? err.message : String(err);
    });
  }
}
