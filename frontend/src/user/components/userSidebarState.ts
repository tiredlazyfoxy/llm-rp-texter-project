import { makeAutoObservable, runInAction } from "mobx";
import { listMyChats, listPublicWorlds } from "../../api/chat";

/**
 * Sidebar-wide MobX state shared across the User SPA.
 *
 * Singleton instance (`userSidebarState`) is mounted once by
 * `UserSidebar` and observed for re-renders. Other state (e.g.
 * `chatPageState.updateSettings`) calls `refreshSidebarChats()` so
 * a name change on the active chat is reflected in the sidebar list
 * immediately, without remounting the component.
 */
export class UserSidebarState {
  worlds: WorldInfo[] = [];
  chats: ChatSessionItem[] = [];
  loaded = false;

  constructor() {
    makeAutoObservable(this);
  }
}

export const userSidebarState = new UserSidebarState();

/** Initial load — fetches both worlds and chats in parallel. */
export async function loadSidebar(state: UserSidebarState): Promise<void> {
  const [worlds, chats] = await Promise.all([
    listPublicWorlds().catch(() => [] as WorldInfo[]),
    listMyChats().catch(() => [] as ChatSessionItem[]),
  ]);
  runInAction(() => {
    state.worlds = worlds;
    state.chats = chats;
    state.loaded = true;
  });
}

/** Refetch only the chat list — used when a chat field changes (e.g. character_name). */
export async function refreshSidebarChats(state: UserSidebarState = userSidebarState): Promise<void> {
  try {
    const chats = await listMyChats();
    runInAction(() => { state.chats = chats; });
  } catch {
    // Silent — sidebar refresh is best-effort.
  }
}
