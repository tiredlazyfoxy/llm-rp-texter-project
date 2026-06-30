import type { TuningProfile, UpdateTuningProfile } from "../types/tuningProfile";
import { request } from "./client";

export async function getTuningProfile(worldId: string, signal?: AbortSignal): Promise<TuningProfile> {
  return request<TuningProfile>(`/api/chats/tuning-profile/${worldId}`, { signal });
}

export async function updateTuningProfile(
  worldId: string,
  body: UpdateTuningProfile,
  signal?: AbortSignal,
): Promise<TuningProfile> {
  return request<TuningProfile>(`/api/chats/tuning-profile/${worldId}`, {
    method: "PUT",
    body,
    signal,
  });
}
