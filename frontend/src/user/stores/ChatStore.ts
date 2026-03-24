import { makeAutoObservable, observable, runInAction } from "mobx";
import * as chatApi from "../../api/chat";

class ChatStore {
  publicWorlds: WorldInfo[] = [];
  myChatList: ChatSessionItem[] = [];
  currentChat: ChatDetail | null = null;
  isLoading = false;
  isSending = false;
  error: string | null = null;
  memories: ChatSummaryItem[] = [];

  // Summary state
  summaries: ChatSummary[] = [];
  expandedSummaryMessages: Map<string, ChatMessage[]> = observable.map();
  isCompacting = false;
  isRegeneratingSummary: string | null = null;

  // Pending user input (kept until backend ack, restored on error)
  pendingInput = "";

  // Streaming state
  streamingContent = "";
  streamingThinking = "";
  streamingToolCalls: Array<{ tool_name: string; arguments: Record<string, string>; result?: string }> = [];
  isThinking = false;

  // Variant state — index the user is currently viewing (for auto-commit on send)
  viewingVariantIndex: number | null = null;

  // Debug & pipeline state
  debugMode = false;
  currentPhase: "planning" | "writing" | null = null;
  currentStatus: string | null = null;

  private _abortController: AbortController | null = null;

  constructor() {
    makeAutoObservable(this);
    this.debugMode = localStorage.getItem("chatDebugMode") === "true";
  }

  toggleDebugMode(): void {
    this.debugMode = !this.debugMode;
    localStorage.setItem("chatDebugMode", String(this.debugMode));
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
      // Insert any summaries whose end_turn < this message's turn
      while (sumIdx < sums.length && sums[sumIdx].end_turn < msg.turn_number) {
        items.push(sums[sumIdx]);
        sumIdx++;
      }
      items.push(msg);
    }
    // Append remaining summaries (if messages list is empty or all messages are before summaries)
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

  async loadPublicWorlds(): Promise<void> {
    try {
      const worlds = await chatApi.listPublicWorlds();
      runInAction(() => { this.publicWorlds = worlds; });
    } catch (e) {
      runInAction(() => { this.error = String(e); });
    }
  }

  async loadMyChatList(): Promise<void> {
    try {
      const items = await chatApi.listMyChats();
      runInAction(() => { this.myChatList = items; });
    } catch (e) {
      runInAction(() => { this.error = String(e); });
    }
  }

  async loadChatDetail(chatId: string): Promise<void> {
    runInAction(() => { this.isLoading = true; this.error = null; });
    try {
      const detail = await chatApi.getChatDetail(chatId);
      runInAction(() => {
        this.currentChat = detail;
        this.summaries = detail.summaries ?? [];
        this.expandedSummaryMessages.clear();
      });
    } catch (e) {
      runInAction(() => { this.error = String(e); });
    } finally {
      runInAction(() => { this.isLoading = false; });
    }
  }

  async createNewChat(req: CreateChatRequest): Promise<string> {
    const session = await chatApi.createChat(req);
    return session.id;
  }

  async sendMessage(content: string): Promise<void> {
    if (!this.currentChat || this.isSending) return;
    const chatId = this.currentChat.session.id;

    // Capture variant selection for atomic send
    const variantIdx = this.viewingVariantIndex;

    runInAction(() => {
      this.isSending = true;
      this.error = null;
      this.pendingInput = content;
      this.streamingContent = "";
      this.streamingThinking = "";
      this.streamingToolCalls = [];
      this.isThinking = false;
      this.currentPhase = null;
      this.currentStatus = null;
      this.viewingVariantIndex = null;
      // Clear variants immediately — server clears them on send
      if (this.currentChat) this.currentChat.variants = [];
    });

    const req: SendMessageRequest = { content };
    if (variantIdx !== null) req.variant_index = variantIdx;

    await new Promise<void>((resolve) => {
      this._abortController = chatApi.sendMessage(
        chatId,
        req,
        {
          onToken: (t) => runInAction(() => { this.streamingContent += t; }),
          onThinking: (t) => runInAction(() => { this.streamingThinking += t; }),
          onThinkingDone: () => runInAction(() => { this.isThinking = false; }),
          onToolCallStart: (name, args) => {
            console.debug("[Chat] tool_call_start:", name, args);
            runInAction(() => {
              this.streamingToolCalls.push({ tool_name: name, arguments: args });
            });
          },
          onToolCallResult: (name, result) => {
            console.debug("[Chat] tool_call_result:", name, result?.slice(0, 200));
            runInAction(() => {
              const tc = this.streamingToolCalls.find((t) => t.tool_name === name && !t.result);
              if (tc) tc.result = result;
            });
          },
          onUserAck: (ack) =>
            runInAction(() => {
              if (this.currentChat) {
                // Avoid duplicate if message already exists (e.g. after edit+resend)
                const exists = this.currentChat.messages.some((m) => m.id === ack.id);
                if (!exists) {
                  this.currentChat.messages.push({
                    id: ack.id,
                    role: "user",
                    content,
                    turn_number: ack.turn_number,
                    tool_calls: null,
                    generation_plan: null,
                    thinking_content: null,
                    is_active_variant: true,
                    created_at: ack.created_at,
                  });
                }
              }
            }),
          onPhase: (phase) => runInAction(() => { this.currentPhase = phase; }),
          onStatus: (text) => runInAction(() => { this.currentStatus = text; }),
          onStatUpdate: (stats) => runInAction(() => {
            if (this.currentChat) {
              const snap = this.currentSnapshot;
              if (snap) Object.assign(snap.character_stats, stats);
            }
          }),
          onDone: (message) => {
            console.debug("[Chat] done, message:", message.id);
            runInAction(() => {
              if (this.currentChat) {
                this.currentChat.messages.push(message);
                this.currentChat.variants = [];
                this.currentChat.session.current_turn = message.turn_number;
              }
              this.pendingInput = "";
              this.streamingContent = "";
              this.isSending = false;
              this.currentPhase = null;
              this.currentStatus = null;
            });
            resolve();
          },
          onError: (detail) => {
            console.error("[Chat] error:", detail);
            runInAction(() => {
              this.error = detail;
              this.isSending = false;
              this.isThinking = false;
              this.currentPhase = null;
              this.currentStatus = null;
              // Keep streamingContent/streamingThinking/streamingToolCalls
              // so the user can see what was collected before the error
            });
            resolve();
          },
        },
      );
    });
  }

  async retryAfterError(): Promise<void> {
    if (this.pendingInput) {
      const content = this.pendingInput;
      await this.sendMessage(content);
      return;
    }
    // No pending input = regeneration error, retry regenerate
    await this.regenerate();
  }

  async regenerate(): Promise<void> {
    if (!this.currentChat || this.isSending) return;
    const chatId = this.currentChat.session.id;
    runInAction(() => {
      this.isSending = true;
      this.error = null;
      this.streamingContent = "";
      this.streamingThinking = "";
      this.streamingToolCalls = [];
      this.currentPhase = null;
      this.currentStatus = null;
      // Don't remove old message — server moves it to variants.
      // On done we reload detail; on error the message stays visible.
    });

    await new Promise<void>((resolve) => {
      this._abortController = chatApi.regenerateMessage(chatId, {
        onToken: (t) => runInAction(() => { this.streamingContent += t; }),
        onThinking: (t) => runInAction(() => { this.streamingThinking += t; }),
        onThinkingDone: () => runInAction(() => { this.isThinking = false; }),
        onToolCallStart: (name, args) =>
          runInAction(() => {
            this.streamingToolCalls.push({ tool_name: name, arguments: args });
          }),
        onToolCallResult: (name, result) =>
          runInAction(() => {
            const tc = this.streamingToolCalls.find((t) => t.tool_name === name && !t.result);
            if (tc) tc.result = result;
          }),
        onPhase: (phase) => runInAction(() => { this.currentPhase = phase; }),
        onStatus: (text) => runInAction(() => { this.currentStatus = text; }),
        onStatUpdate: () => {},
        onDone: (message) => {
          const reloadId = this.currentChat?.session.id;
          runInAction(() => {
            if (this.currentChat) {
              // Replace old assistant message at this turn with the new one
              const msgs = this.currentChat.messages;
              const oldIdx = msgs.findLastIndex(
                (m) => m.role === "assistant" && m.turn_number === message.turn_number,
              );
              if (oldIdx >= 0) {
                msgs[oldIdx] = message;
              } else {
                msgs.push(message);
              }
              this.currentChat.session.current_turn = message.turn_number;
            }
            this.streamingContent = "";
            this.isSending = false;
            this.currentPhase = null;
            this.currentStatus = null;
            this.viewingVariantIndex = null;
          });
          // Reload to get updated variants from server
          if (reloadId) this.loadChatDetail(reloadId);
          resolve();
        },
        onError: (detail) => {
          runInAction(() => {
            this.error = detail;
            this.isSending = false;
            this.isThinking = false;
            this.currentPhase = null;
            this.currentStatus = null;
          });
          // Reload to restore the message from server variants
          if (this.currentChat) this.loadChatDetail(this.currentChat.session.id);
          resolve();
        },
      });
    });
  }

  async continueWithVariant(variantIndex: number): Promise<void> {
    if (!this.currentChat) return;
    await chatApi.continueChat(this.currentChat.session.id, { variant_index: variantIndex });
    this.viewingVariantIndex = null;
    await this.loadChatDetail(this.currentChat.session.id);
  }

  async rewindToTurn(turn: number): Promise<void> {
    if (!this.currentChat) return;
    const detail = await chatApi.rewindChat(this.currentChat.session.id, { target_turn: turn });
    runInAction(() => {
      this.currentChat = detail;
      this.summaries = detail.summaries ?? [];
      this.expandedSummaryMessages.clear();
    });
  }

  async updateSettings(req: UpdateChatSettingsRequest): Promise<void> {
    if (!this.currentChat) return;
    await chatApi.updateChatSettings(this.currentChat.session.id, req);
    await this.loadChatDetail(this.currentChat.session.id);
  }

  async archiveChat(): Promise<void> {
    if (!this.currentChat) return;
    await chatApi.archiveChat(this.currentChat.session.id);
    runInAction(() => {
      if (this.currentChat) this.currentChat.session.status = "archived";
    });
  }

  async deleteChat(chatId: string): Promise<void> {
    await chatApi.deleteChat(chatId);
    runInAction(() => {
      this.myChatList = this.myChatList.filter((c) => c.id !== chatId);
      if (this.currentChat?.session.id === chatId) this.currentChat = null;
    });
  }

  stopGeneration(): void {
    this._abortController?.abort();
    runInAction(() => { this.isSending = false; this.pendingInput = ""; this.streamingContent = ""; });
  }

  async loadMemories(): Promise<void> {
    if (!this.currentChat) return;
    const mems = await chatApi.listChatMemories(this.currentChat.session.id);
    runInAction(() => { this.memories = mems; });
  }

  async deleteMemory(memoryId: string): Promise<void> {
    if (!this.currentChat) return;
    await chatApi.deleteChatMemory(this.currentChat.session.id, memoryId);
    runInAction(() => { this.memories = this.memories.filter((m) => m.id !== memoryId); });
  }

  // ------- Summary / compaction actions -------

  async compactUpTo(messageId: string): Promise<void> {
    if (!this.currentChat || this.isCompacting) return;
    const chatId = this.currentChat.session.id;
    runInAction(() => { this.isCompacting = true; });
    try {
      const resp = await chatApi.compactChat(chatId, { up_to_message_id: messageId });
      runInAction(() => {
        this.summaries.push(resp.summary);
        // Remove compacted messages from the active messages list
        if (this.currentChat) {
          const endMsgId = resp.summary.end_message_id;
          const startMsgId = resp.summary.start_message_id;
          let removing = false;
          this.currentChat.messages = this.currentChat.messages.filter((m) => {
            if (m.id === startMsgId) removing = true;
            if (removing) {
              const isEnd = m.id === endMsgId;
              if (isEnd) removing = false;
              return false; // remove
            }
            return true;
          });
        }
      });
    } catch (e) {
      runInAction(() => { this.error = String(e); });
    } finally {
      runInAction(() => { this.isCompacting = false; });
    }
  }

  async regenerateSummary(summaryId: string): Promise<void> {
    if (!this.currentChat) return;
    const chatId = this.currentChat.session.id;
    runInAction(() => { this.isRegeneratingSummary = summaryId; });
    try {
      const updated = await chatApi.regenerateSummary(chatId, summaryId);
      runInAction(() => {
        const idx = this.summaries.findIndex((s) => s.id === summaryId);
        if (idx !== -1) this.summaries[idx] = updated;
      });
    } catch (e) {
      runInAction(() => { this.error = String(e); });
    } finally {
      runInAction(() => { this.isRegeneratingSummary = null; });
    }
  }

  async expandSummary(summaryId: string): Promise<void> {
    if (!this.currentChat || this.expandedSummaryMessages.has(summaryId)) return;
    const chatId = this.currentChat.session.id;
    try {
      const messages = await chatApi.getOriginalMessages(chatId, summaryId);
      runInAction(() => { this.expandedSummaryMessages.set(summaryId, messages); });
    } catch (e) {
      runInAction(() => { this.error = String(e); });
    }
  }

  collapseSummary(summaryId: string): void {
    this.expandedSummaryMessages.delete(summaryId);
  }

  // ------- Message management actions -------

  async editMessage(messageId: string, newContent: string): Promise<void> {
    if (!this.currentChat) return;
    const chatId = this.currentChat.session.id;
    try {
      const detail = await chatApi.editMessage(chatId, messageId, newContent);
      runInAction(() => {
        this.currentChat = detail;
        this.summaries = detail.summaries ?? [];
        this.expandedSummaryMessages.clear();
      });
      // Re-generate with the edited content
      await this.sendMessage(newContent);
    } catch (e) {
      runInAction(() => { this.error = String(e); });
    }
  }

  async deleteMessage(messageId: string): Promise<void> {
    if (!this.currentChat) return;
    const chatId = this.currentChat.session.id;
    try {
      const detail = await chatApi.deleteMessage(chatId, messageId);
      runInAction(() => {
        this.currentChat = detail;
        this.summaries = detail.summaries ?? [];
        this.expandedSummaryMessages.clear();
      });
    } catch (e) {
      runInAction(() => { this.error = String(e); });
    }
  }

  async regenerateAtTurn(turnNumber: number): Promise<void> {
    if (!this.currentChat || this.isSending) return;
    const chatId = this.currentChat.session.id;
    runInAction(() => {
      this.isSending = true;
      this.streamingContent = "";
      this.streamingThinking = "";
      this.streamingToolCalls = [];
      this.currentPhase = null;
      this.currentStatus = null;
    });

    await new Promise<void>((resolve) => {
      this._abortController = chatApi.regenerateMessage(chatId, {
        onToken: (t) => runInAction(() => { this.streamingContent += t; }),
        onThinking: (t) => runInAction(() => { this.streamingThinking += t; }),
        onThinkingDone: () => runInAction(() => { this.isThinking = false; }),
        onToolCallStart: (name, args) =>
          runInAction(() => {
            this.streamingToolCalls.push({ tool_name: name, arguments: args });
          }),
        onToolCallResult: (name, result) =>
          runInAction(() => {
            const tc = this.streamingToolCalls.find((t) => t.tool_name === name && !t.result);
            if (tc) tc.result = result;
          }),
        onPhase: (phase) => runInAction(() => { this.currentPhase = phase; }),
        onStatus: (text) => runInAction(() => { this.currentStatus = text; }),
        onStatUpdate: () => {},
        onDone: (_message) => {
          // Reload full detail since rewind may have changed state
          this.loadChatDetail(chatId).then(() => resolve());
          runInAction(() => {
            this.streamingContent = "";
            this.isSending = false;
            this.currentPhase = null;
            this.currentStatus = null;
          });
        },
        onError: (detail) => {
          runInAction(() => {
            this.error = detail;
            this.isSending = false;
            this.isThinking = false;
            this.currentPhase = null;
            this.currentStatus = null;
          });
          resolve();
        },
      }, turnNumber);
    });
  }
}

export const chatStore = new ChatStore();
