import { makeAutoObservable, runInAction } from "mobx";
import { listMyChats, deleteChat } from "../../api/chat";

type AsyncStatus = "idle" | "loading" | "ready" | "error";

/**
 * Page state for `ChatListPage` (`/`).
 *
 * Holds the list of the current user's chats plus the delete-confirm
 * modal target. Mutations that touch the network live as external
 * `(state, signal)` functions below.
 */
export class ChatListPageState {
  chats: ChatSessionItem[] = [];
  chatsStatus: AsyncStatus = "idle";
  chatsError: string | null = null;

  deleteTarget: ChatSessionItem | null = null;
  deleteStatus: AsyncStatus = "idle";
  deleteError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

export async function loadChats(state: ChatListPageState, signal: AbortSignal): Promise<void> {
  state.chatsStatus = "loading";
  state.chatsError = null;
  try {
    const chats = await listMyChats(signal);
    runInAction(() => {
      state.chats = chats;
      state.chatsStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.chatsStatus = "error";
      state.chatsError = err instanceof Error ? err.message : String(err);
    });
  }
}

export async function deleteSelectedChat(state: ChatListPageState, signal: AbortSignal): Promise<void> {
  const target = state.deleteTarget;
  if (!target) return;
  state.deleteStatus = "loading";
  state.deleteError = null;
  try {
    await deleteChat(target.id, signal);
    runInAction(() => {
      state.chats = state.chats.filter((c) => c.id !== target.id);
      state.deleteTarget = null;
      state.deleteStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.deleteStatus = "error";
      state.deleteError = err instanceof Error ? err.message : String(err);
    });
  }
}
