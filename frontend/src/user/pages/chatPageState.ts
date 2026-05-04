import { makeAutoObservable, observable, runInAction } from "mobx";
import * as chatApi from "../../api/chat";
import { extractUserInstructions } from "../../utils/oocParser";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

interface StreamingToolCallInfo {
  tool_name: string;
  arguments: Record<string, string>;
  result?: string;
  stage_name?: string;
}

/**
 * Page state for `ChatViewPage` (`/chat/:chatId`).
 *
 * One instance per mount, owned by the page. Path-param change
 * remounts via the `key={chatId}` route wrapper.
 */
export class ChatPageState {
  chatId: string;

  currentChat: ChatDetail | null = null;
  loadStatus: AsyncStatus = "idle";
  loadError: string | null = null;

  world: WorldInfo | null = null;

  summaries: ChatSummary[] = [];
  expandedSummaryMessages: Map<string, ChatMessage[]> = observable.map();
  memories: ChatMemoryItem[] = [];

  isSending = false;
  pendingInput = "";
  streamingContent = "";
  streamingThinking = "";
  streamingToolCalls: StreamingToolCallInfo[] = [];
  isThinking = false;
  currentPhase: "planning" | "writing" | null = null;
  currentStatus: string | null = null;

  viewingVariantIndex: number | null = null;

  isCompacting = false;
  compactPhase: string | null = null;
  compactToolCalls: StreamingToolCallInfo[] = [];
  compactStreamingContent = "";
  isRegeneratingSummary: string | null = null;

  error: string | null = null;

  debugMode = false;

  streamCtrl: AbortController | null = null;

  constructor(chatId: string) {
    this.chatId = chatId;
    this.debugMode = localStorage.getItem("chatDebugMode") === "true";
    makeAutoObservable(this, { streamCtrl: false });
  }

  get activeMessages(): ChatMessage[] {
    return this.currentChat?.messages ?? [];
  }

  /** Interleaved summaries + non-summarized messages in chronological order. */
  get displayItems(): Array<ChatSummary | ChatMessage> {
    const msgs = this.activeMessages;
    const sums = this.summaries;
    if (!sums.length) return msgs;

    const items: Array<ChatSummary | ChatMessage> = [];
    let sumIdx = 0;
    for (const msg of msgs) {
      while (sumIdx < sums.length && sums[sumIdx].end_turn < msg.turn_number) {
        items.push(sums[sumIdx]);
        sumIdx++;
      }
      items.push(msg);
    }
    while (sumIdx < sums.length) {
      items.push(sums[sumIdx]);
      sumIdx++;
    }
    return items;
  }

  get latestTurnVariants(): GenerationVariant[] {
    return this.currentChat?.variants ?? [];
  }

  get hasMultipleVariants(): boolean {
    return this.latestTurnVariants.length > 0;
  }

  get currentSnapshot(): ChatStateSnapshot | null {
    const snaps = this.currentChat?.snapshots ?? [];
    const turn = this.currentChat?.session.current_turn ?? 0;
    return snaps.find((s) => s.turn_number === turn) ?? snaps[snaps.length - 1] ?? null;
  }

  /** Snapshot reflecting the currently viewed variant's stats, or currentSnapshot if none. */
  get displaySnapshot(): ChatStateSnapshot | null {
    if (this.viewingVariantIndex != null) {
      const variants = this.latestTurnVariants;
      const v = variants[this.viewingVariantIndex];
      if (v?.character_stats) {
        return {
          turn_number: this.currentChat?.session.current_turn ?? 0,
          location_id: v.location_id ?? null,
          location_name: v.location_name ?? null,
          character_stats: v.character_stats,
          world_stats: v.world_stats ?? {},
        };
      }
    }
    return this.currentSnapshot;
  }

  /** Aborts any active SSE stream owned by this page. */
  dispose(): void {
    this.streamCtrl?.abort();
    this.streamCtrl = null;
  }
}

/** Patch currentChat in place instead of replacing it.
 *  Preserves MobX observable identity so only changed properties trigger re-renders. */
function mergeChatDetail(state: ChatPageState, detail: ChatDetail): void {
  const current = state.currentChat;
  if (!current) {
    state.currentChat = detail;
    state.summaries = detail.summaries ?? [];
    state.expandedSummaryMessages.clear();
    return;
  }

  Object.assign(current.session, detail.session);

  const existingById = new Map(current.messages.map((m) => [m.id, m]));
  current.messages.length = 0;
  for (const msg of detail.messages) {
    const existing = existingById.get(msg.id);
    if (existing) {
      Object.assign(existing, msg);
      current.messages.push(existing);
    } else {
      current.messages.push(msg);
    }
  }

  const oldVarLen = current.variants.length;
  for (let i = 0; i < detail.variants.length; i++) {
    if (i < oldVarLen) {
      Object.assign(current.variants[i], detail.variants[i]);
    } else {
      current.variants.push(detail.variants[i]);
    }
  }
  current.variants.length = detail.variants.length;

  const existingSnapByTurn = new Map(current.snapshots.map((s) => [s.turn_number, s]));
  current.snapshots.length = 0;
  for (const snap of detail.snapshots) {
    const existing = existingSnapByTurn.get(snap.turn_number);
    if (existing) {
      Object.assign(existing, snap);
      current.snapshots.push(existing);
    } else {
      current.snapshots.push(snap);
    }
  }

  const existingSumById = new Map(state.summaries.map((s) => [s.id, s]));
  state.summaries.length = 0;
  for (const sum of detail.summaries ?? []) {
    const existing = existingSumById.get(sum.id);
    if (existing) {
      Object.assign(existing, sum);
      state.summaries.push(existing);
    } else {
      state.summaries.push(sum);
    }
  }
  state.expandedSummaryMessages.clear();
}

/** Apply a stat_update SSE event: upsert snapshot at the given turn. */
function applyStatUpdate(
  state: ChatPageState,
  data: {
    character_stats: Record<string, number | string | string[]>;
    world_stats: Record<string, number | string | string[]>;
    turn_number: number;
  },
): void {
  if (!state.currentChat) return;
  const snaps = state.currentChat.snapshots;
  const existing = snaps.find((s) => s.turn_number === data.turn_number);
  if (existing) {
    existing.character_stats = data.character_stats;
    existing.world_stats = data.world_stats;
  } else {
    snaps.push({
      turn_number: data.turn_number,
      location_id: state.currentChat.session.current_location_id ?? null,
      location_name: null,
      character_stats: data.character_stats,
      world_stats: data.world_stats,
    });
  }
}

export async function loadChat(state: ChatPageState, signal: AbortSignal): Promise<void> {
  state.loadStatus = "loading";
  state.loadError = null;
  try {
    const detail = await chatApi.getChatDetail(state.chatId, signal);
    runInAction(() => {
      if (state.currentChat?.session.id === state.chatId) {
        mergeChatDetail(state, detail);
      } else {
        state.currentChat = detail;
        state.summaries = detail.summaries ?? [];
        state.expandedSummaryMessages.clear();
      }
      state.loadStatus = "ready";
    });
    // Load matching world (for stat definitions in StatsPanel) and memories in parallel
    const worldId = detail.session.world_id;
    chatApi.listPublicWorlds(signal).then((worlds) => {
      if (signal.aborted) return;
      const found = worlds.find((w) => w.id === worldId) ?? null;
      runInAction(() => { state.world = found; });
    }).catch(() => {});
    loadMemories(state, signal).catch(() => {});
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.loadStatus = "error";
      state.loadError = err instanceof Error ? err.message : String(err);
    });
  }
}

export async function loadMemories(state: ChatPageState, signal?: AbortSignal): Promise<void> {
  if (!state.currentChat) return;
  try {
    const mems = await chatApi.listChatMemories(state.currentChat.session.id, signal);
    runInAction(() => { state.memories = mems; });
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => { state.error = err instanceof Error ? err.message : String(err); });
  }
}

export async function sendMessage(
  state: ChatPageState,
  content: string,
  userInstructions?: string,
): Promise<void> {
  if (!state.currentChat || state.isSending) return;
  const chatId = state.currentChat.session.id;
  const variantIdx = state.viewingVariantIndex;

  runInAction(() => {
    state.isSending = true;
    state.error = null;
    state.pendingInput = content;
    state.streamingContent = "";
    state.streamingThinking = "";
    state.streamingToolCalls = [];
    state.isThinking = false;
    state.currentPhase = null;
    state.currentStatus = null;
    state.viewingVariantIndex = null;
    if (state.currentChat) state.currentChat.variants.length = 0;
  });

  const req: SendMessageRequest = { content };
  if (variantIdx !== null) req.variant_index = variantIdx;
  if (userInstructions) req.user_instructions = userInstructions;

  await new Promise<void>((resolve) => {
    state.streamCtrl = chatApi.sendMessage(chatId, req, {
      onToken: (t) => runInAction(() => { state.streamingContent += t; }),
      onThinking: (t) => runInAction(() => { state.streamingThinking += t; }),
      onThinkingDone: () => runInAction(() => { state.isThinking = false; }),
      onToolCallStart: (name, args, stageName) => {
        console.debug("[Chat] tool_call_start:", name, args, stageName);
        runInAction(() => {
          state.streamingToolCalls.push({ tool_name: name, arguments: args, stage_name: stageName });
        });
      },
      onToolCallResult: (name, result) => {
        console.debug("[Chat] tool_call_result:", name, result?.slice(0, 200));
        runInAction(() => {
          const tc = state.streamingToolCalls.find((t) => t.tool_name === name && !t.result);
          if (tc) tc.result = result;
        });
      },
      onUserAck: (ack) =>
        runInAction(() => {
          if (!state.currentChat) return;
          const existing = state.currentChat.messages.find((m) => m.id === ack.id);
          if (existing) {
            existing.content = content;
            existing.user_instructions = userInstructions ?? null;
          } else {
            state.currentChat.messages.push({
              id: ack.id,
              role: "user",
              content,
              turn_number: ack.turn_number,
              tool_calls: null,
              generation_plan: null,
              thinking_content: null,
              user_instructions: userInstructions ?? null,
              is_active_variant: true,
              created_at: ack.created_at,
            });
          }
        }),
      onPhase: (phase) => runInAction(() => { state.currentPhase = phase; }),
      onStatus: (text) => runInAction(() => { state.currentStatus = text; }),
      onStatUpdate: (data) => runInAction(() => { applyStatUpdate(state, data); }),
      onDone: (message) => {
        console.debug("[Chat] done, message:", message.id);
        runInAction(() => {
          if (state.currentChat) {
            state.currentChat.messages.push(message);
            state.currentChat.variants.length = 0;
            state.currentChat.session.current_turn = message.turn_number;
          }
          state.pendingInput = "";
          state.streamingContent = "";
          state.isSending = false;
          state.currentPhase = null;
          state.currentStatus = null;
        });
        loadMemories(state).catch(() => {});
        resolve();
      },
      onError: (detail) => {
        console.error("[Chat] error:", detail);
        runInAction(() => {
          state.error = detail;
          state.isSending = false;
          state.isThinking = false;
          state.currentPhase = null;
          state.currentStatus = null;
        });
        resolve();
      },
    });
  });
}

export async function retryAfterError(state: ChatPageState): Promise<void> {
  if (state.pendingInput) {
    const content = state.pendingInput;
    await sendMessage(state, content);
    return;
  }
  await regenerate(state);
}

export async function regenerate(state: ChatPageState): Promise<void> {
  if (!state.currentChat || state.isSending) return;
  const chatId = state.currentChat.session.id;
  runInAction(() => {
    state.isSending = true;
    state.error = null;
    state.streamingContent = "";
    state.streamingThinking = "";
    state.streamingToolCalls = [];
    state.currentPhase = null;
    state.currentStatus = null;
  });

  await new Promise<void>((resolve) => {
    state.streamCtrl = chatApi.regenerateMessage(chatId, {
      onToken: (t) => runInAction(() => { state.streamingContent += t; }),
      onThinking: (t) => runInAction(() => { state.streamingThinking += t; }),
      onThinkingDone: () => runInAction(() => { state.isThinking = false; }),
      onToolCallStart: (name, args, stageName) =>
        runInAction(() => {
          state.streamingToolCalls.push({ tool_name: name, arguments: args, stage_name: stageName });
        }),
      onToolCallResult: (name, result) =>
        runInAction(() => {
          const tc = state.streamingToolCalls.find((t) => t.tool_name === name && !t.result);
          if (tc) tc.result = result;
        }),
      onPhase: (phase) => runInAction(() => { state.currentPhase = phase; }),
      onStatus: (text) => runInAction(() => { state.currentStatus = text; }),
      onStatUpdate: (data) => runInAction(() => { applyStatUpdate(state, data); }),
      onVariantsUpdate: (variants) => runInAction(() => {
        if (!state.currentChat) return;
        const cur = state.currentChat.variants;
        const oldLen = cur.length;
        for (let i = 0; i < variants.length; i++) {
          if (i < oldLen) {
            Object.assign(cur[i], variants[i]);
          } else {
            cur.push(variants[i]);
          }
        }
        cur.length = variants.length;
      }),
      onDone: (message) => {
        runInAction(() => {
          if (state.currentChat) {
            const msgs = state.currentChat.messages;
            const oldIdx = msgs.findLastIndex(
              (m) => m.role === "assistant" && m.turn_number === message.turn_number,
            );
            if (oldIdx >= 0) msgs[oldIdx] = message;
            else msgs.push(message);
            state.currentChat.session.current_turn = message.turn_number;
          }
          state.streamingContent = "";
          state.isSending = false;
          state.currentPhase = null;
          state.currentStatus = null;
          state.viewingVariantIndex = null;
        });
        loadMemories(state).catch(() => {});
        resolve();
      },
      onError: (detail) => {
        runInAction(() => {
          state.error = detail;
          state.isSending = false;
          state.isThinking = false;
          state.currentPhase = null;
          state.currentStatus = null;
        });
        if (state.currentChat) {
          const ctrl = new AbortController();
          chatApi.getChatDetail(state.currentChat.session.id, ctrl.signal)
            .then((d) => runInAction(() => { mergeChatDetail(state, d); }))
            .catch(() => {});
        }
        resolve();
      },
    });
  });
}

export async function regenerateAtTurn(state: ChatPageState, turnNumber: number): Promise<void> {
  if (!state.currentChat || state.isSending) return;
  const chatId = state.currentChat.session.id;
  runInAction(() => {
    state.isSending = true;
    state.streamingContent = "";
    state.streamingThinking = "";
    state.streamingToolCalls = [];
    state.currentPhase = null;
    state.currentStatus = null;
  });

  await new Promise<void>((resolve) => {
    state.streamCtrl = chatApi.regenerateMessage(chatId, {
      onToken: (t) => runInAction(() => { state.streamingContent += t; }),
      onThinking: (t) => runInAction(() => { state.streamingThinking += t; }),
      onThinkingDone: () => runInAction(() => { state.isThinking = false; }),
      onToolCallStart: (name, args, stageName) =>
        runInAction(() => {
          state.streamingToolCalls.push({ tool_name: name, arguments: args, stage_name: stageName });
        }),
      onToolCallResult: (name, result) =>
        runInAction(() => {
          const tc = state.streamingToolCalls.find((t) => t.tool_name === name && !t.result);
          if (tc) tc.result = result;
        }),
      onPhase: (phase) => runInAction(() => { state.currentPhase = phase; }),
      onStatus: (text) => runInAction(() => { state.currentStatus = text; }),
      onStatUpdate: (data) => runInAction(() => { applyStatUpdate(state, data); }),
      onVariantsUpdate: (variants) => runInAction(() => {
        if (!state.currentChat) return;
        const cur = state.currentChat.variants;
        const oldLen = cur.length;
        for (let i = 0; i < variants.length; i++) {
          if (i < oldLen) {
            Object.assign(cur[i], variants[i]);
          } else {
            cur.push(variants[i]);
          }
        }
        cur.length = variants.length;
      }),
      onDone: (_message) => {
        const ctrl = new AbortController();
        chatApi.getChatDetail(chatId, ctrl.signal)
          .then((d) => runInAction(() => { mergeChatDetail(state, d); }))
          .catch(() => {})
          .finally(() => resolve());
        runInAction(() => {
          state.streamingContent = "";
          state.isSending = false;
          state.currentPhase = null;
          state.currentStatus = null;
        });
      },
      onError: (detail) => {
        runInAction(() => {
          state.error = detail;
          state.isSending = false;
          state.isThinking = false;
          state.currentPhase = null;
          state.currentStatus = null;
        });
        resolve();
      },
    }, turnNumber);
  });
}

export function stopGeneration(state: ChatPageState): void {
  state.streamCtrl?.abort();
  runInAction(() => {
    state.isSending = false;
    state.pendingInput = "";
    state.streamingContent = "";
  });
}

export async function continueWithVariant(
  state: ChatPageState,
  variantIndex: number,
  signal?: AbortSignal,
): Promise<void> {
  if (!state.currentChat) return;
  const chatId = state.currentChat.session.id;
  await chatApi.continueChat(chatId, { variant_index: variantIndex }, signal);
  state.viewingVariantIndex = null;
  const detail = await chatApi.getChatDetail(chatId, signal);
  runInAction(() => { mergeChatDetail(state, detail); });
}

export async function rewindToTurn(
  state: ChatPageState,
  turn: number,
  signal?: AbortSignal,
): Promise<void> {
  if (!state.currentChat) return;
  const detail = await chatApi.rewindChat(state.currentChat.session.id, { target_turn: turn }, signal);
  runInAction(() => { mergeChatDetail(state, detail); });
}

export async function updateSettings(
  state: ChatPageState,
  req: UpdateChatSettingsRequest,
  signal?: AbortSignal,
): Promise<void> {
  if (!state.currentChat) return;
  await chatApi.updateChatSettings(state.currentChat.session.id, req, signal);
  runInAction(() => {
    if (!state.currentChat) return;
    if (req.tool_model) state.currentChat.session.tool_model = req.tool_model;
    if (req.text_model) state.currentChat.session.text_model = req.text_model;
  });
}

export async function archiveChat(state: ChatPageState, signal?: AbortSignal): Promise<void> {
  if (!state.currentChat) return;
  await chatApi.archiveChat(state.currentChat.session.id, signal);
  runInAction(() => {
    if (state.currentChat) state.currentChat.session.status = "archived";
  });
}

export async function deleteCurrentChat(state: ChatPageState, signal?: AbortSignal): Promise<void> {
  if (!state.currentChat) return;
  await chatApi.deleteChat(state.currentChat.session.id, signal);
}

export async function editMessage(
  state: ChatPageState,
  messageId: string,
  rawContent: string,
): Promise<void> {
  if (!state.currentChat) return;
  const chatId = state.currentChat.session.id;
  try {
    const { content, userInstructions } = extractUserInstructions(rawContent);
    const detail = await chatApi.editMessage(chatId, messageId, content);
    runInAction(() => { mergeChatDetail(state, detail); });
    await sendMessage(state, content, userInstructions ?? undefined);
  } catch (err) {
    runInAction(() => { state.error = err instanceof Error ? err.message : String(err); });
  }
}

export async function deleteMessage(
  state: ChatPageState,
  messageId: string,
  signal?: AbortSignal,
): Promise<void> {
  if (!state.currentChat) return;
  const chatId = state.currentChat.session.id;
  try {
    const detail = await chatApi.deleteMessage(chatId, messageId, signal);
    runInAction(() => { mergeChatDetail(state, detail); });
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => { state.error = err instanceof Error ? err.message : String(err); });
  }
}

export async function deleteMemory(
  state: ChatPageState,
  memoryId: string,
  signal?: AbortSignal,
): Promise<void> {
  if (!state.currentChat) return;
  await chatApi.deleteChatMemory(state.currentChat.session.id, memoryId, signal);
  runInAction(() => { state.memories = state.memories.filter((m) => m.id !== memoryId); });
}

export async function compactUpTo(
  state: ChatPageState,
  messageId: string,
  variantIndex?: number,
): Promise<void> {
  if (!state.currentChat || state.isCompacting) return;
  const chatId = state.currentChat.session.id;
  runInAction(() => {
    state.isCompacting = true;
    state.compactPhase = null;
    state.compactToolCalls = [];
    state.compactStreamingContent = "";
  });

  const req: CompactRequest = { up_to_message_id: messageId };
  if (variantIndex != null) req.variant_index = variantIndex;

  await new Promise<void>((resolve) => {
    state.streamCtrl = chatApi.compactChatStream(chatId, req, {
      onPhase: (phase) => runInAction(() => { state.compactPhase = phase; }),
      onToken: (content) => runInAction(() => { state.compactStreamingContent += content; }),
      onToolCallStart: (name, args, stageName) =>
        runInAction(() => {
          state.compactToolCalls.push({ tool_name: name, arguments: args, stage_name: stageName });
        }),
      onToolCallResult: (name, result) =>
        runInAction(() => {
          const tc = state.compactToolCalls.find((t) => t.tool_name === name && !t.result);
          if (tc) tc.result = result;
        }),
      onDone: (resp) => {
        runInAction(() => {
          state.summaries.push(resp.summary);
          if (state.currentChat) {
            const endMsgId = resp.summary.end_message_id;
            const startMsgId = resp.summary.start_message_id;
            let removing = false;
            state.currentChat.messages = state.currentChat.messages.filter((m) => {
              if (m.id === startMsgId) removing = true;
              if (removing) {
                const isEnd = m.id === endMsgId;
                if (isEnd) removing = false;
                return false;
              }
              return true;
            });
            if (resp.summary.end_turn >= state.currentChat.session.current_turn) {
              state.currentChat.variants.length = 0;
            }
          }
          state.isCompacting = false;
          state.compactPhase = null;
          state.compactToolCalls = [];
          state.compactStreamingContent = "";
        });
        loadMemories(state).catch(() => {});
        resolve();
      },
      onError: (detail) => {
        runInAction(() => {
          state.error = detail;
          state.isCompacting = false;
          state.compactPhase = null;
          state.compactToolCalls = [];
          state.compactStreamingContent = "";
        });
        resolve();
      },
    });
  });
}

export async function unsummarizeLast(
  state: ChatPageState,
  summaryId: string,
  signal?: AbortSignal,
): Promise<void> {
  if (!state.currentChat) return;
  const chatId = state.currentChat.session.id;
  try {
    const restoredMessages = await chatApi.unsummarizeLast(chatId, summaryId, signal);
    runInAction(() => {
      state.summaries = state.summaries.filter((s) => s.id !== summaryId);
      if (state.currentChat) {
        const msgs = state.currentChat.messages;
        for (const rm of restoredMessages) msgs.push(rm);
        msgs.sort((a, b) => a.turn_number - b.turn_number);
      }
      state.expandedSummaryMessages.delete(summaryId);
    });
    loadMemories(state).catch(() => {});
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => { state.error = err instanceof Error ? err.message : String(err); });
  }
}

export async function regenerateSummary(
  state: ChatPageState,
  summaryId: string,
  signal?: AbortSignal,
): Promise<void> {
  if (!state.currentChat) return;
  const chatId = state.currentChat.session.id;
  runInAction(() => { state.isRegeneratingSummary = summaryId; });
  try {
    const updated = await chatApi.regenerateSummary(chatId, summaryId, signal);
    runInAction(() => {
      const idx = state.summaries.findIndex((s) => s.id === summaryId);
      if (idx !== -1) state.summaries[idx] = updated;
    });
  } catch (err) {
    if (!signal?.aborted) {
      runInAction(() => { state.error = err instanceof Error ? err.message : String(err); });
    }
  } finally {
    runInAction(() => { state.isRegeneratingSummary = null; });
  }
}

export async function expandSummary(
  state: ChatPageState,
  summaryId: string,
  signal?: AbortSignal,
): Promise<void> {
  if (!state.currentChat || state.expandedSummaryMessages.has(summaryId)) return;
  const chatId = state.currentChat.session.id;
  try {
    const messages = await chatApi.getOriginalMessages(chatId, summaryId, signal);
    runInAction(() => { state.expandedSummaryMessages.set(summaryId, messages); });
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => { state.error = err instanceof Error ? err.message : String(err); });
  }
}

export function collapseSummary(state: ChatPageState, summaryId: string): void {
  state.expandedSummaryMessages.delete(summaryId);
}

export function toggleDebugMode(state: ChatPageState): void {
  state.debugMode = !state.debugMode;
  localStorage.setItem("chatDebugMode", String(state.debugMode));
}
