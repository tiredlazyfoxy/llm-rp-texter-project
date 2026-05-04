import { makeAutoObservable, runInAction } from "mobx";
import type {
  ChatMessage,
  EditorLlmParams,
  LlmChatRequest,
  SSEHandlers,
  ToolCallEntry,
} from "../../../types/llmChat";
import type { EnabledModelInfo } from "../../../types/llmServer";
import { fetchEnabledModels, streamChat } from "../../../api/llmChat";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

const LS_MODEL_KEY = "llmrp_editor_model";
const LS_PARAMS_KEY = "llmrp_editor_params";

export const DEFAULT_LLM_PARAMS: EditorLlmParams = {
  temperature: 0.7,
  top_p: 1.0,
  repetition_penalty: 1.0,
  enable_thinking: false,
  enable_tools: false,
};

function loadParamsFromStorage(): EditorLlmParams {
  try {
    const raw = localStorage.getItem(LS_PARAMS_KEY);
    if (raw) return { ...DEFAULT_LLM_PARAMS, ...JSON.parse(raw) };
  } catch {
    /* ignore */
  }
  return { ...DEFAULT_LLM_PARAMS };
}

/**
 * Per-mount internal state for `LlmChatPanel`. Owned by the component
 * via `useState(() => new LlmChatPanelState())`. Public props of the
 * panel are unchanged; this class lives behind them.
 */
export class LlmChatPanelState {
  models: EnabledModelInfo[] = [];
  modelsStatus: AsyncStatus = "idle";
  modelsError: string | null = null;

  selectedModel: string | null = null;

  params: EditorLlmParams = { ...DEFAULT_LLM_PARAMS };
  paramsOpen = false;

  messages: ChatMessage[] = [];
  isStreaming = false;

  /** Non-observable — mutated mid-stream. */
  abortCtrl: AbortController | null = null;

  constructor() {
    this.selectedModel = localStorage.getItem(LS_MODEL_KEY);
    this.params = loadParamsFromStorage();
    makeAutoObservable<this, "abortCtrl">(this, { abortCtrl: false });
  }

  get modelOptions(): { value: string; label: string }[] {
    return this.models.map((m) => ({
      value: m.model_id,
      label: `${m.model_id} (${m.server_name})`,
    }));
  }
}

/** Caller-supplied request context used by send / regenerate flows. */
export interface LlmChatRequestContext {
  currentContent: string;
  worldId?: string;
  docId?: string;
  docType?: "location" | "npc" | "lore_fact";
  fieldType?: "description" | "system_prompt" | "initial_message" | "pipeline_prompt";
}

export async function loadModels(
  state: LlmChatPanelState,
  signal: AbortSignal,
): Promise<void> {
  state.modelsStatus = "loading";
  state.modelsError = null;
  try {
    const list = await fetchEnabledModels(signal);
    if (signal.aborted) return;
    runInAction(() => {
      state.models = list;
      state.modelsStatus = "ready";
      // If the saved model is no longer enabled, drop it.
      if (state.selectedModel && !list.some((m) => m.model_id === state.selectedModel)) {
        state.selectedModel = null;
        localStorage.removeItem(LS_MODEL_KEY);
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

export function setSelectedModel(state: LlmChatPanelState, modelId: string | null): void {
  state.selectedModel = modelId;
  if (modelId) localStorage.setItem(LS_MODEL_KEY, modelId);
  else localStorage.removeItem(LS_MODEL_KEY);
}

export function setParam<K extends keyof EditorLlmParams>(
  state: LlmChatPanelState,
  key: K,
  value: EditorLlmParams[K],
): void {
  state.params = { ...state.params, [key]: value };
  localStorage.setItem(LS_PARAMS_KEY, JSON.stringify(state.params));
}

export function setParamsOpen(state: LlmChatPanelState, open: boolean): void {
  state.paramsOpen = open;
}

function startStream(
  state: LlmChatPanelState,
  baseMessages: ChatMessage[],
  ctx: LlmChatRequestContext,
): void {
  if (!state.selectedModel) return;

  const assistantMsg: ChatMessage = {
    id: crypto.randomUUID(),
    role: "assistant",
    content: "",
    thinkingContent: "",
    isStreaming: true,
  };

  runInAction(() => {
    state.messages = [...baseMessages, assistantMsg];
    state.isStreaming = true;
  });

  const apiMessages = state.messages
    .filter((m) => !m.isStreaming)
    .map((m) => ({ role: m.role, content: m.content }));

  const req: LlmChatRequest = {
    model_id: state.selectedModel,
    messages: apiMessages,
    temperature: state.params.temperature,
    top_p: state.params.top_p,
    repetition_penalty: state.params.repetition_penalty,
    enable_thinking: state.params.enable_thinking,
    enable_tools: state.params.enable_tools,
    current_content: ctx.currentContent,
    world_id: ctx.worldId ?? null,
    doc_id: ctx.docId ?? "",
    doc_type: ctx.docType ?? "",
    field_type: ctx.fieldType ?? "",
  };

  const updateLastAssistant = (
    mut: (msg: ChatMessage) => ChatMessage,
  ): void => {
    runInAction(() => {
      const last = state.messages[state.messages.length - 1];
      if (!last || last.role !== "assistant") return;
      state.messages = [...state.messages.slice(0, -1), mut(last)];
    });
  };

  const handlers: SSEHandlers = {
    onToken: (content) => {
      updateLastAssistant((m) => ({ ...m, content: m.content + content }));
    },
    onThinking: (content) => {
      updateLastAssistant((m) => ({
        ...m,
        thinkingContent: (m.thinkingContent || "") + content,
      }));
    },
    onThinkingDone: () => {
      // No-op — thinking content is already accumulated.
    },
    onToolCallStart: (tool_name, args) => {
      updateLastAssistant((m) => {
        const entry: ToolCallEntry = { tool_name, arguments: args };
        return { ...m, toolCalls: [...(m.toolCalls ?? []), entry] };
      });
    },
    onToolCallResult: (tool_name, result) => {
      updateLastAssistant((m) => {
        const calls = [...(m.toolCalls ?? [])];
        const idx = calls.findLastIndex(
          (c) => c.tool_name === tool_name && c.result === undefined,
        );
        if (idx !== -1) calls[idx] = { ...calls[idx], result };
        return { ...m, toolCalls: calls };
      });
    },
    onDone: (content) => {
      runInAction(() => {
        const last = state.messages[state.messages.length - 1];
        if (last && last.role === "assistant") {
          state.messages = [
            ...state.messages.slice(0, -1),
            { ...last, content, isStreaming: false },
          ];
        }
        state.isStreaming = false;
        state.abortCtrl = null;
      });
    },
    onError: (message) => {
      runInAction(() => {
        const last = state.messages[state.messages.length - 1];
        if (last && last.role === "assistant") {
          state.messages = [
            ...state.messages.slice(0, -1),
            {
              ...last,
              content: last.content || `Error: ${message}`,
              isStreaming: false,
            },
          ];
        }
        state.isStreaming = false;
        state.abortCtrl = null;
      });
    },
  };

  state.abortCtrl = streamChat(req, handlers);
}

export function sendChatMessage(
  state: LlmChatPanelState,
  text: string,
  ctx: LlmChatRequestContext,
): void {
  const trimmed = text.trim();
  if (!trimmed || state.isStreaming || !state.selectedModel) return;
  const userMsg: ChatMessage = {
    id: crypto.randomUUID(),
    role: "user",
    content: trimmed,
  };
  startStream(state, [...state.messages, userMsg], ctx);
}

export function stopChat(state: LlmChatPanelState): void {
  state.abortCtrl?.abort();
  runInAction(() => {
    const last = state.messages[state.messages.length - 1];
    if (last && last.role === "assistant") {
      state.messages = [
        ...state.messages.slice(0, -1),
        { ...last, isStreaming: false },
      ];
    }
    state.isStreaming = false;
    state.abortCtrl = null;
  });
}

export function regenerateLast(
  state: LlmChatPanelState,
  ctx: LlmChatRequestContext,
): void {
  if (state.isStreaming) return;
  const trimmed =
    state.messages.length > 0 &&
    state.messages[state.messages.length - 1].role === "assistant"
      ? state.messages.slice(0, -1)
      : state.messages.slice();
  startStream(state, trimmed, ctx);
}

export function regenerateAtMessage(
  state: LlmChatPanelState,
  messageId: string,
  ctx: LlmChatRequestContext,
): void {
  if (state.isStreaming) return;
  const idx = state.messages.findIndex((m) => m.id === messageId);
  if (idx === -1) return;
  const truncated = state.messages.slice(0, idx);
  startStream(state, truncated, ctx);
}

export function deleteMessage(state: LlmChatPanelState, messageId: string): void {
  state.messages = state.messages.filter((m) => m.id !== messageId);
}

export function clearMessages(state: LlmChatPanelState): void {
  if (state.isStreaming) stopChat(state);
  state.messages = [];
}
