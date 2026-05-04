import { makeAutoObservable, runInAction } from "mobx";
import type {
  PipelineConfig,
  PipelineConfigOptions,
  PipelineItem,
} from "../../types/pipeline";
import type { EnabledModelInfo } from "../../types/llmServer";
import { fetchEnabledModels } from "../../api/llmChat";
import {
  getPipeline,
  getPipelineConfigOptions,
  updatePipeline,
} from "../../api/pipelines";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

/**
 * Page state for `PipelineStageEditPage`
 * (`/admin/pipelines/:pipelineId/stage/:stageIndex`).
 *
 * Edits a single stage of an existing pipeline. The stage edit is
 * persisted via `updatePipeline` against the full `pipeline_config`
 * (only the indexed stage changes).
 */
export class PipelineStageEditPageState {
  pipelineId: string;
  stageIndex: number;

  pipeline: PipelineItem | null = null;
  loadStatus: AsyncStatus = "idle";
  loadError: string | null = null;

  configOptions: PipelineConfigOptions | null = null;
  configOptionsStatus: AsyncStatus = "idle";
  configOptionsError: string | null = null;

  enabledModels: EnabledModelInfo[] = [];
  enabledModelsStatus: AsyncStatus = "idle";
  enabledModelsError: string | null = null;

  // Stage draft
  content = "";
  stageEnabled = true;
  stageModelId: string | null = null;

  // Read-only stage info
  stageName = "";
  stepType = "";
  stageTools: string[] = [];

  // Baselines for isDirty
  originalContent = "";
  originalStageEnabled = true;
  originalStageModelId: string | null = null;

  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;
  successMessage: string | null = null;

  // Local snapshot of the parsed pipeline_config so saveStage can
  // reconstruct the full config without re-parsing.
  private pipelineConfig: PipelineConfig = { stages: [] };

  constructor(pipelineId: string, stageIndex: number) {
    this.pipelineId = pipelineId;
    this.stageIndex = stageIndex;
    makeAutoObservable<this, "pipelineConfig">(this, { pipelineConfig: false });
  }

  get isDirty(): boolean {
    return (
      this.content !== this.originalContent ||
      this.stageEnabled !== this.originalStageEnabled ||
      this.stageModelId !== this.originalStageModelId
    );
  }

  get canSubmit(): boolean {
    return this.isDirty && this.saveStatus !== "loading";
  }

  /** Internal: expose pipelineConfig to module-level `saveStage`. */
  _getPipelineConfig(): PipelineConfig {
    return this.pipelineConfig;
  }

  /** Internal: replace pipelineConfig snapshot. */
  _setPipelineConfig(cfg: PipelineConfig): void {
    this.pipelineConfig = cfg;
  }
}

export async function loadStage(
  state: PipelineStageEditPageState,
  signal: AbortSignal,
): Promise<void> {
  if (!state.pipelineId) {
    state.loadStatus = "error";
    state.loadError = "Invalid pipeline ID";
    return;
  }
  state.loadStatus = "loading";
  state.loadError = null;
  state.configOptionsStatus = "loading";
  state.enabledModelsStatus = "loading";

  // Fire models concurrently with main load.
  const modelsPromise = fetchEnabledModels(signal)
    .then((list) => {
      runInAction(() => {
        state.enabledModels = list;
        state.enabledModelsStatus = "ready";
      });
    })
    .catch((err: unknown) => {
      if (signal.aborted) return;
      runInAction(() => {
        state.enabledModelsStatus = "error";
        state.enabledModelsError = err instanceof Error ? err.message : String(err);
      });
    });

  try {
    const [p, opts] = await Promise.all([
      getPipeline(state.pipelineId, signal),
      getPipelineConfigOptions(signal),
    ]);
    if (signal.aborted) return;
    let parsed: PipelineConfig = { stages: [] };
    try {
      const obj = JSON.parse(p.pipeline_config || "{}");
      parsed = { stages: Array.isArray(obj.stages) ? obj.stages : [] };
    } catch {
      parsed = { stages: [] };
    }
    if (state.stageIndex < 0 || state.stageIndex >= parsed.stages.length) {
      runInAction(() => {
        state.pipeline = p;
        state.configOptions = opts;
        state.configOptionsStatus = "ready";
        state.loadStatus = "error";
        state.loadError = `Stage ${state.stageIndex} not found`;
      });
      await modelsPromise;
      return;
    }
    const stage = parsed.stages[state.stageIndex];
    runInAction(() => {
      state.pipeline = p;
      state._setPipelineConfig(parsed);
      state.configOptions = opts;
      state.configOptionsStatus = "ready";
      state.content = stage.prompt;
      state.originalContent = stage.prompt;
      state.stepType = stage.step_type;
      state.stageName = stage.name || "";
      state.stageTools = stage.tools || [];
      state.stageEnabled = stage.enabled !== false;
      state.originalStageEnabled = stage.enabled !== false;
      state.stageModelId = stage.model_id ?? null;
      state.originalStageModelId = stage.model_id ?? null;
      state.loadStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.loadStatus = "error";
      state.loadError = err instanceof Error ? err.message : String(err);
    });
  }

  await modelsPromise;
}

export async function saveStage(
  state: PipelineStageEditPageState,
  signal: AbortSignal,
): Promise<void> {
  if (!state.canSubmit) return;
  state.saveStatus = "loading";
  state.saveError = null;
  state.successMessage = null;
  try {
    const current = state._getPipelineConfig();
    const updatedCfg: PipelineConfig = {
      stages: current.stages.map((s, i) =>
        i === state.stageIndex
          ? {
              ...s,
              prompt: state.content,
              enabled: state.stageEnabled,
              model_id: state.stageModelId,
            }
          : s,
      ),
    };
    await updatePipeline(
      state.pipelineId,
      { pipeline_config: JSON.stringify(updatedCfg) },
      signal,
    );
    runInAction(() => {
      state._setPipelineConfig(updatedCfg);
      state.originalContent = state.content;
      state.originalStageEnabled = state.stageEnabled;
      state.originalStageModelId = state.stageModelId;
      state.saveStatus = "ready";
      state.successMessage = "Applied.";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.saveStatus = "error";
      state.saveError = err instanceof Error ? err.message : String(err);
    });
  }
}

/**
 * Replace `state.content` with the appropriate default template for
 * the current step type. Caller is expected to have confirmed via
 * `window.confirm` if `state.content` is non-empty.
 */
export function loadDefaultTemplate(state: PipelineStageEditPageState): void {
  if (!state.configOptions) return;
  const templates = state.configOptions.default_templates;
  const isToolStep = state.stepType === "tool" || state.stepType === "planning";
  state.content = isToolStep ? templates.tool : templates.writer;
}
