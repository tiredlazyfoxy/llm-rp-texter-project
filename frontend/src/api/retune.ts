import type { RetuneStatus } from "../types/retune";
import { request } from "./client";

/** Start a background retune for the chat's session. Returns the fresh status. */
export async function triggerRetune(chatId: string, signal?: AbortSignal): Promise<RetuneStatus> {
  return request<RetuneStatus>(`/api/chats/${chatId}/retune`, { method: "POST", signal });
}

/** Cancel the running background retune for the chat's session (no restart). */
export async function stopRetune(chatId: string, signal?: AbortSignal): Promise<RetuneStatus> {
  return request<RetuneStatus>(`/api/chats/${chatId}/retune/stop`, { method: "POST", signal });
}

/** Poll the running flag plus the current (user, world) profile values. */
export async function getRetuneStatus(chatId: string, signal?: AbortSignal): Promise<RetuneStatus> {
  return request<RetuneStatus>(`/api/chats/${chatId}/retune/status`, { signal });
}
