import { makeAutoObservable, runInAction } from "mobx";
import * as chatApi from "../../api/chat";

class ChatStore {
  publicWorlds: WorldInfo[] = [];
  myChatList: ChatSessionItem[] = [];
  currentChat: ChatDetail | null = null;
  isLoading = false;
  isSending = false;
  error: string | null = null;
  memories: ChatSummaryItem[] = [];

  // Streaming state
  streamingContent = "";
  streamingThinking = "";
  streamingToolCalls: Array<{ tool_name: string; arguments: Record<string, string>; result?: string }> = [];
  isThinking = false;

  private _abortController: AbortController | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  get activeMessages(): ChatMessage[] {
    return this.currentChat?.messages ?? [];
  }

  get latestTurnVariants(): ChatMessage[] {
    return this.currentChat?.variants ?? [];
  }

  get hasMultipleVariants(): boolean {
    return this.latestTurnVariants.length > 1;
  }

  get currentSnapshot(): ChatStateSnapshot | null {
    const snaps = this.currentChat?.snapshots ?? [];
    const turn = this.currentChat?.session.current_turn ?? 0;
    return snaps.find((s) => s.turn_number === turn) ?? snaps[snaps.length - 1] ?? null;
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
      runInAction(() => { this.currentChat = detail; });
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
    runInAction(() => {
      this.isSending = true;
      this.streamingContent = "";
      this.streamingThinking = "";
      this.streamingToolCalls = [];
      this.isThinking = false;
    });

    await new Promise<void>((resolve) => {
      this._abortController = chatApi.sendMessage(
        chatId,
        { content },
        {
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
          onStatUpdate: (stats) => runInAction(() => {
            if (this.currentChat) {
              const snap = this.currentSnapshot;
              if (snap) Object.assign(snap.character_stats, stats);
            }
          }),
          onDone: (message) => {
            runInAction(() => {
              if (this.currentChat) {
                this.currentChat.messages.push(message);
                this.currentChat.variants = [message];
                this.currentChat.session.current_turn = message.turn_number;
              }
              this.streamingContent = "";
              this.isSending = false;
            });
            resolve();
          },
          onError: (detail) => {
            runInAction(() => {
              this.error = detail;
              this.isSending = false;
              this.streamingContent = "";
            });
            resolve();
          },
        },
      );
    });
  }

  async regenerate(): Promise<void> {
    if (!this.currentChat || this.isSending) return;
    const chatId = this.currentChat.session.id;
    runInAction(() => {
      this.isSending = true;
      this.streamingContent = "";
      this.streamingThinking = "";
      this.streamingToolCalls = [];
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
        onStatUpdate: () => {},
        onDone: (message) => {
          runInAction(() => {
            if (this.currentChat) {
              this.currentChat.variants = [...this.currentChat.variants, message];
            }
            this.streamingContent = "";
            this.isSending = false;
          });
          resolve();
        },
        onError: (detail) => {
          runInAction(() => {
            this.error = detail;
            this.isSending = false;
            this.streamingContent = "";
          });
          resolve();
        },
      });
    });
  }

  async continueWithVariant(variantId: string): Promise<void> {
    if (!this.currentChat) return;
    await chatApi.continueChat(this.currentChat.session.id, { selected_variant_id: variantId });
    await this.loadChatDetail(this.currentChat.session.id);
  }

  async rewindToTurn(turn: number): Promise<void> {
    if (!this.currentChat) return;
    const detail = await chatApi.rewindChat(this.currentChat.session.id, { target_turn: turn });
    runInAction(() => { this.currentChat = detail; });
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
    runInAction(() => { this.isSending = false; this.streamingContent = ""; });
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
}

export const chatStore = new ChatStore();
