import { makeAutoObservable, runInAction } from "mobx";
import type { PipelineItem } from "../../types/pipeline";
import {
  deletePipeline as apiDeletePipeline,
  listPipelines,
} from "../../api/pipelines";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

/**
 * Page state for `PipelinesListPage` (`/admin/pipelines`).
 *
 * Holds the pipelines list trio. Row click + clone + create-new are
 * navigation actions handled by the page itself via `useNavigate`.
 */
export class PipelinesListPageState {
  pipelines: PipelineItem[] = [];
  pipelinesStatus: AsyncStatus = "idle";
  pipelinesError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

export async function loadPipelines(
  state: PipelinesListPageState,
  signal: AbortSignal,
): Promise<void> {
  state.pipelinesStatus = "loading";
  state.pipelinesError = null;
  try {
    const pipelines = await listPipelines(signal);
    runInAction(() => {
      state.pipelines = pipelines;
      state.pipelinesStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.pipelinesStatus = "error";
      state.pipelinesError = err instanceof Error ? err.message : String(err);
    });
  }
}

export async function deletePipeline(
  state: PipelinesListPageState,
  pipelineId: string,
  signal: AbortSignal,
): Promise<void> {
  try {
    await apiDeletePipeline(pipelineId, signal);
    await loadPipelines(state, signal);
  } catch (err) {
    if (signal.aborted) return;
    const msg = err instanceof Error ? err.message : String(err);
    runInAction(() => {
      if (/referenced/i.test(msg)) {
        state.pipelinesError =
          "This pipeline is referenced by one or more worlds — re-point them first.";
      } else {
        state.pipelinesError = msg;
      }
    });
  }
}
