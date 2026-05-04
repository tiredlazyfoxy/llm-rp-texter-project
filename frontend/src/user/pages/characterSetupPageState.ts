import { makeAutoObservable, runInAction } from "mobx";
import type { EnabledModelInfo } from "../../types/llmServer";
import { listPublicWorlds, createChat } from "../../api/chat";
import { fetchModelsForSettings } from "../../api/userSettings";
import { loadToolModel, loadTextModel } from "../../utils/modelSettings";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

/**
 * Page state for `CharacterSetupPage` (`/worlds/:worldId/new`).
 *
 * Holds the world + available models trios plus the form draft
 * (placeholder variables, starting location, tool/text model). All
 * loads + submit live as external `(state, signal)` functions below.
 */
export class CharacterSetupPageState {
  worldId: string;

  world: WorldInfo | null = null;
  worldStatus: AsyncStatus = "idle";
  worldError: string | null = null;

  availableModels: EnabledModelInfo[] = [];
  modelsStatus: AsyncStatus = "idle";
  modelsError: string | null = null;

  variables: Record<string, string> = {};
  locationId = "";
  toolModel: ModelConfig;
  textModel: ModelConfig;

  submitStatus: AsyncStatus = "idle";
  submitError: string | null = null;

  constructor(worldId: string) {
    this.worldId = worldId;
    this.toolModel = loadToolModel();
    this.textModel = loadTextModel();
    makeAutoObservable(this);
  }

  get placeholders(): string[] {
    if (!this.world) return [];
    return [
      ...new Set(
        [...this.world.character_template.matchAll(/\{([A-Z_]+)\}/g)].map((m) => m[1]),
      ),
    ];
  }

  get canSubmit(): boolean {
    return this.world !== null && this.submitStatus !== "loading";
  }
}

async function loadWorld(state: CharacterSetupPageState, signal: AbortSignal): Promise<void> {
  state.worldStatus = "loading";
  state.worldError = null;
  try {
    const worlds = await listPublicWorlds(signal);
    const found = worlds.find((w) => w.id === state.worldId) ?? null;
    runInAction(() => {
      if (!found) {
        state.worldStatus = "error";
        state.worldError = "World not found";
        return;
      }
      state.world = found;
      state.worldStatus = "ready";
      const phs = [
        ...new Set(
          [...found.character_template.matchAll(/\{([A-Z_]+)\}/g)].map((m) => m[1]),
        ),
      ];
      state.variables = Object.fromEntries(phs.map((p) => [p, ""]));
      if (found.locations.length > 0) state.locationId = found.locations[0].id;
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.worldStatus = "error";
      state.worldError = err instanceof Error ? err.message : String(err);
    });
  }
}

async function loadModels(state: CharacterSetupPageState, signal: AbortSignal): Promise<void> {
  state.modelsStatus = "loading";
  state.modelsError = null;
  try {
    const models = await fetchModelsForSettings(signal);
    runInAction(() => {
      state.availableModels = models;
      state.modelsStatus = "ready";
      if (models.length > 0) {
        const ids = models.map((m) => m.model_id);
        if (!ids.includes(state.toolModel.model_id ?? "")) {
          state.toolModel = { ...state.toolModel, model_id: models[0].model_id };
        }
        if (!ids.includes(state.textModel.model_id ?? "")) {
          state.textModel = { ...state.textModel, model_id: models[0].model_id };
        }
      }
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.modelsStatus = "error";
      state.modelsError = err instanceof Error ? err.message : String(err);
    });
  }
}

export async function loadCharacterSetup(
  state: CharacterSetupPageState,
  signal: AbortSignal,
): Promise<void> {
  await Promise.all([loadWorld(state, signal), loadModels(state, signal)]);
}

export async function submitCharacter(
  state: CharacterSetupPageState,
  signal: AbortSignal,
): Promise<string | null> {
  if (!state.world) return null;
  state.submitStatus = "loading";
  state.submitError = null;
  try {
    const placeholders = state.placeholders;
    const session = await createChat(
      {
        world_id: state.worldId,
        character_name:
          state.variables["NAME"] || state.variables[placeholders[0]] || "Hero",
        template_variables: state.variables,
        starting_location_id: state.locationId,
        tool_model: state.toolModel,
        text_model: state.textModel,
      },
      signal,
    );
    runInAction(() => {
      state.submitStatus = "ready";
    });
    return session.id;
  } catch (err) {
    if (signal.aborted) return null;
    runInAction(() => {
      state.submitStatus = "error";
      state.submitError = err instanceof Error ? err.message : String(err);
    });
    return null;
  }
}
