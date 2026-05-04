import { makeAutoObservable, runInAction } from "mobx";
import { ApiError } from "../../api/client";
import type {
  CreatePipelineRequest,
  PipelineConfig,
  PipelineConfigOptions,
  PipelineItem,
  PipelineStage,
  UpdatePipelineRequest,
} from "../../types/pipeline";
import type { EnabledModelInfo } from "../../types/llmServer";
import { fetchEnabledModels } from "../../api/llmChat";
import {
  createPipeline,
  deletePipeline as apiDeletePipeline,
  getPipeline,
  getPipelineConfigOptions,
  updatePipeline,
} from "../../api/pipelines";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

export type PipelineEditMode = "shadow" | "edit";

export interface PipelineDraft {
  name: string;
  description: string;
  kind: string;
  system_prompt: string;
  simple_tools: string[];
  pipeline_config: PipelineConfig;
  agent_config: string;
}

export type PipelineDraftErrors = Partial<Record<keyof PipelineDraft, string>>;

const DRAFT_FIELD_KEYS: Record<keyof PipelineDraft, true> = {
  name: true,
  description: true,
  kind: true,
  system_prompt: true,
  simple_tools: true,
  pipeline_config: true,
  agent_config: true,
};

function emptyDraft(): PipelineDraft {
  return {
    name: "",
    description: "",
    kind: "simple",
    system_prompt: "",
    simple_tools: [],
    pipeline_config: { stages: [] },
    agent_config: "{}",
  };
}

function draftFromPipeline(p: PipelineItem): PipelineDraft {
  let simpleTools: string[] = [];
  try {
    const parsed = JSON.parse(p.simple_tools || "[]");
    if (Array.isArray(parsed)) simpleTools = parsed.filter((s): s is string => typeof s === "string");
  } catch {
    simpleTools = [];
  }
  let pipelineConfig: PipelineConfig = { stages: [] };
  try {
    const parsed = JSON.parse(p.pipeline_config || "{}");
    pipelineConfig = { stages: Array.isArray(parsed.stages) ? parsed.stages : [] };
  } catch {
    pipelineConfig = { stages: [] };
  }
  return {
    name: p.name,
    description: p.description,
    kind: p.kind,
    system_prompt: p.system_prompt,
    simple_tools: simpleTools,
    pipeline_config: pipelineConfig,
    agent_config: p.agent_config ?? "{}",
  };
}

function clonedDraftFromSource(src: PipelineItem): PipelineDraft {
  const base = draftFromPipeline(src);
  base.name = `${src.name} (clone)`;
  return base;
}

function configEquals(a: PipelineConfig, b: PipelineConfig): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

function draftsEqual(a: PipelineDraft, b: PipelineDraft): boolean {
  return (
    a.name === b.name &&
    a.description === b.description &&
    a.kind === b.kind &&
    a.system_prompt === b.system_prompt &&
    a.simple_tools.length === b.simple_tools.length &&
    a.simple_tools.every((t, i) => t === b.simple_tools[i]) &&
    configEquals(a.pipeline_config, b.pipeline_config) &&
    a.agent_config === b.agent_config
  );
}

/**
 * Page state for `PipelineEditPage` (`/admin/pipelines/new` and
 * `/admin/pipelines/:pipelineId`).
 *
 * Shadow mode: `pipelineId === null`. The draft starts blank or pre-fills
 * from `cloneFromId`; saving POSTs and returns the new id so the page
 * can navigate.
 *
 * Edit mode: `pipelineId !== null`. The draft mirrors the loaded record;
 * saving PUTs and refreshes the snapshot.
 */
export class PipelineEditPageState {
  pipelineId: string | null;
  cloneFromId: string | null;

  pipeline: PipelineItem | null = null;
  loadStatus: AsyncStatus = "idle";
  loadError: string | null = null;

  configOptions: PipelineConfigOptions | null = null;
  configOptionsStatus: AsyncStatus = "idle";
  configOptionsError: string | null = null;

  enabledModels: EnabledModelInfo[] = [];
  enabledModelsStatus: AsyncStatus = "idle";
  enabledModelsError: string | null = null;

  draft: PipelineDraft = emptyDraft();
  baselineDraft: PipelineDraft = emptyDraft();
  serverErrors: PipelineDraftErrors = {};

  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;
  saveSuccess: string | null = null;

  deleteStatus: AsyncStatus = "idle";

  expandedStages: Set<number> = new Set();

  constructor(pipelineId: string | null, cloneFromId: string | null) {
    this.pipelineId = pipelineId;
    this.cloneFromId = cloneFromId;
    makeAutoObservable(this);
  }

  get mode(): PipelineEditMode {
    return this.pipelineId === null ? "shadow" : "edit";
  }

  get errors(): PipelineDraftErrors {
    const e: PipelineDraftErrors = {};
    if (!this.draft.name.trim()) e.name = "Name is required";
    return { ...e, ...this.serverErrors };
  }

  get isValid(): boolean {
    return Object.keys(this.errors).length === 0;
  }

  get isDirty(): boolean {
    return !draftsEqual(this.draft, this.baselineDraft);
  }

  get canSubmit(): boolean {
    return this.isValid && this.isDirty && this.saveStatus !== "loading";
  }
}

export async function loadPipelineEdit(
  state: PipelineEditPageState,
  signal: AbortSignal,
): Promise<void> {
  state.loadStatus = "loading";
  state.loadError = null;
  state.configOptionsStatus = "loading";
  state.configOptionsError = null;
  state.enabledModelsStatus = "loading";
  state.enabledModelsError = null;

  // Fire config-options + models concurrently with main load.
  const optsPromise = getPipelineConfigOptions(signal)
    .then((opts) => {
      runInAction(() => {
        state.configOptions = opts;
        state.configOptionsStatus = "ready";
      });
    })
    .catch((err: unknown) => {
      if (signal.aborted) return;
      runInAction(() => {
        state.configOptionsStatus = "error";
        state.configOptionsError = err instanceof Error ? err.message : String(err);
      });
    });

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
    if (state.mode === "shadow") {
      let initial: PipelineDraft;
      if (state.cloneFromId) {
        const src = await getPipeline(state.cloneFromId, signal);
        initial = clonedDraftFromSource(src);
      } else {
        initial = emptyDraft();
      }
      if (signal.aborted) return;
      runInAction(() => {
        state.pipeline = null;
        state.draft = initial;
        // Baseline for shadow mode is the *blank* draft so any field
        // change (including from a clone-source) marks the form dirty.
        state.baselineDraft = emptyDraft();
        state.serverErrors = {};
        state.loadStatus = "ready";
      });
    } else {
      if (!state.pipelineId) {
        runInAction(() => {
          state.loadStatus = "error";
          state.loadError = "Invalid pipeline ID";
        });
        return;
      }
      const p = await getPipeline(state.pipelineId, signal);
      if (signal.aborted) return;
      const next = draftFromPipeline(p);
      runInAction(() => {
        state.pipeline = p;
        state.draft = next;
        state.baselineDraft = draftFromPipeline(p);
        state.serverErrors = {};
        state.loadStatus = "ready";
      });
    }
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.loadStatus = "error";
      state.loadError = err instanceof Error ? err.message : String(err);
    });
  }

  await optsPromise;
  await modelsPromise;
}

function mapServerErrors(details: unknown): PipelineDraftErrors {
  const out: PipelineDraftErrors = {};
  if (details && typeof details === "object" && "detail" in details) {
    const detail = (details as { detail: unknown }).detail;
    if (Array.isArray(detail)) {
      for (const entry of detail) {
        if (entry && typeof entry === "object" && "loc" in entry && "msg" in entry) {
          const loc = (entry as { loc: unknown[] }).loc;
          const msg = String((entry as { msg: unknown }).msg);
          const field = loc[loc.length - 1];
          if (typeof field === "string" && field in DRAFT_FIELD_KEYS) {
            out[field as keyof PipelineDraft] = msg;
          }
        }
      }
    }
  }
  return out;
}

/**
 * Persist the current draft. Shadow mode POSTs and returns the new id
 * so the page can navigate; edit mode PUTs and refreshes the snapshot
 * + baseline. Returns `null` when nothing was created (edit mode or
 * the call was aborted).
 */
export async function savePipeline(
  state: PipelineEditPageState,
  signal: AbortSignal,
): Promise<string | null> {
  if (!state.canSubmit) return null;
  state.saveStatus = "loading";
  state.saveError = null;
  state.saveSuccess = null;
  try {
    if (state.mode === "shadow") {
      const req: CreatePipelineRequest = {
        name: state.draft.name,
        description: state.draft.description,
        kind: state.draft.kind,
        system_prompt: state.draft.system_prompt,
        simple_tools: JSON.stringify(state.draft.simple_tools),
        pipeline_config: JSON.stringify(state.draft.pipeline_config),
        agent_config: state.draft.agent_config,
      };
      const created = await createPipeline(req, signal);
      runInAction(() => {
        state.pipeline = created;
        state.serverErrors = {};
        state.saveStatus = "ready";
      });
      return created.id;
    }
    if (!state.pipelineId) return null;
    const req: UpdatePipelineRequest = {
      name: state.draft.name,
      description: state.draft.description,
      kind: state.draft.kind,
      system_prompt: state.draft.system_prompt,
      simple_tools: JSON.stringify(state.draft.simple_tools),
      pipeline_config: JSON.stringify(state.draft.pipeline_config),
    };
    const updated = await updatePipeline(state.pipelineId, req, signal);
    const refreshed = draftFromPipeline(updated);
    runInAction(() => {
      state.pipeline = updated;
      state.draft = refreshed;
      state.baselineDraft = draftFromPipeline(updated);
      state.serverErrors = {};
      state.saveStatus = "ready";
      state.saveSuccess = "Pipeline saved";
    });
    return null;
  } catch (err) {
    if (signal.aborted) return null;
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
    return null;
  }
}

/**
 * Delete the current pipeline (edit mode only). Returns true on success
 * so the page can navigate away.
 */
export async function deleteCurrentPipeline(
  state: PipelineEditPageState,
  signal: AbortSignal,
): Promise<boolean> {
  if (!state.pipelineId) return false;
  state.deleteStatus = "loading";
  try {
    await apiDeletePipeline(state.pipelineId, signal);
    runInAction(() => {
      state.deleteStatus = "ready";
    });
    return true;
  } catch (err) {
    if (signal.aborted) return false;
    const msg = err instanceof Error ? err.message : String(err);
    runInAction(() => {
      state.deleteStatus = "error";
      if (/referenced/i.test(msg)) {
        state.saveError =
          "This pipeline is referenced by one or more worlds — re-point them first.";
      } else {
        state.saveError = msg;
      }
    });
    return false;
  }
}

// ── Stage mutations (local) ────────────────────────────────────

/**
 * Append a stage of `stageType`, or — for `tool` stages — splice in
 * before any existing writer stage, mirroring the legacy form's UX.
 */
export function addStage(state: PipelineEditPageState, stageType: string): void {
  const newStage: PipelineStage = {
    step_type: stageType,
    name: "",
    prompt: "",
    max_agent_steps: stageType === "tool" ? 10 : null,
    tools: [],
    enabled: true,
    model_id: null,
  };
  const stages = [...state.draft.pipeline_config.stages];
  if (stageType === "tool") {
    const writerIdx = stages.findIndex(
      (s) => s.step_type === "writer" || s.step_type === "writing",
    );
    if (writerIdx !== -1) {
      stages.splice(writerIdx, 0, newStage);
      state.draft.pipeline_config = { stages };
      return;
    }
  }
  stages.push(newStage);
  state.draft.pipeline_config = { stages };
}

export function removeStage(state: PipelineEditPageState, idx: number): void {
  const stages = state.draft.pipeline_config.stages.filter((_, i) => i !== idx);
  state.draft.pipeline_config = { stages };
}

export function reorderStages(
  state: PipelineEditPageState,
  fromIdx: number,
  toIdx: number,
): void {
  const stages = [...state.draft.pipeline_config.stages];
  if (fromIdx < 0 || fromIdx >= stages.length || toIdx < 0 || toIdx >= stages.length) return;
  const [moved] = stages.splice(fromIdx, 1);
  stages.splice(toIdx, 0, moved);
  state.draft.pipeline_config = { stages };
}

export function updateStage(
  state: PipelineEditPageState,
  idx: number,
  patch: Partial<PipelineStage>,
): void {
  const stages = [...state.draft.pipeline_config.stages];
  if (idx < 0 || idx >= stages.length) return;
  stages[idx] = { ...stages[idx], ...patch };
  state.draft.pipeline_config = { stages };
}

/** When switching to "chain" with no stages, seed a tool + writer pair. */
export function seedChainStages(state: PipelineEditPageState): void {
  if (state.draft.pipeline_config.stages.length > 0) return;
  state.draft.pipeline_config = {
    stages: [
      { step_type: "tool", name: "", prompt: "", max_agent_steps: 10, tools: [], enabled: true, model_id: null },
      { step_type: "writer", name: "", prompt: "", max_agent_steps: null, tools: [], enabled: true, model_id: null },
    ],
  };
}

export function toggleStageExpanded(state: PipelineEditPageState, idx: number): void {
  const next = new Set(state.expandedStages);
  if (next.has(idx)) next.delete(idx);
  else next.add(idx);
  state.expandedStages = next;
}
