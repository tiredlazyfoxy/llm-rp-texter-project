import { makeAutoObservable, runInAction } from "mobx";
import { listPublicWorlds } from "../../api/chat";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

/**
 * Page state for `WorldPage` (`/worlds/:worldId`).
 *
 * The backend exposes no get-by-id endpoint for public worlds; we
 * load the public list and filter by `worldId` (matches existing
 * behavior). Adding a backend endpoint is out of scope.
 */
export class WorldPageState {
  worldId: string;
  world: WorldInfo | null = null;
  worldStatus: AsyncStatus = "idle";
  worldError: string | null = null;

  constructor(worldId: string) {
    this.worldId = worldId;
    makeAutoObservable(this);
  }
}

export async function loadWorld(state: WorldPageState, signal: AbortSignal): Promise<void> {
  state.worldStatus = "loading";
  state.worldError = null;
  try {
    const worlds = await listPublicWorlds(signal);
    const found = worlds.find((w) => w.id === state.worldId) ?? null;
    runInAction(() => {
      if (found) {
        state.world = found;
        state.worldStatus = "ready";
      } else {
        state.worldStatus = "error";
        state.worldError = "World not found";
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
