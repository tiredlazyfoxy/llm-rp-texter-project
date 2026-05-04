import type { TranslateRequest } from "../types/llmChat";
import type { TranslateStreamHandlers } from "../hooks/useTranslation";
import { authHeaders, request } from "./client";
import { streamTranslate } from "./translateStream";

export interface ChatSSEHandlers {
  onToken?: (content: string) => void;
  onThinking?: (content: string) => void;
  onThinkingDone?: () => void;
  onToolCallStart?: (toolName: string, args: Record<string, string>, stageName?: string) => void;
  onToolCallResult?: (toolName: string, result: string) => void;
  onPhase?: (phase: "planning" | "writing") => void;
  onStatus?: (text: string) => void;
  onStatUpdate?: (data: { character_stats: Record<string, number | string | string[]>; world_stats: Record<string, number | string | string[]>; turn_number: number }) => void;
  onUserAck?: (ack: { id: string; turn_number: number; created_at: string }) => void;
  onVariantsUpdate?: (variants: GenerationVariant[]) => void;
  onDone?: (message: ChatMessage) => void;
  onError?: (detail: string) => void;
}

export function translateTextChat(req: TranslateRequest, handlers: TranslateStreamHandlers): AbortController {
  return streamTranslate("/api/chats/translate", req, handlers);
}

export async function listPublicWorlds(signal?: AbortSignal): Promise<WorldInfo[]> {
  return request<WorldInfo[]>("/api/chats/worlds", { signal });
}

export async function createChat(req: CreateChatRequest, signal?: AbortSignal): Promise<ChatSession> {
  return request<ChatSession>("/api/chats", {
    method: "POST",
    body: req,
    signal,
  });
}

export async function listMyChats(signal?: AbortSignal): Promise<ChatSessionItem[]> {
  const res = await request<{ items: ChatSessionItem[] }>("/api/chats", { signal });
  return res.items;
}

export async function getChatDetail(chatId: string, signal?: AbortSignal): Promise<ChatDetail> {
  return request<ChatDetail>(`/api/chats/${chatId}`, { signal });
}

export async function continueChat(chatId: string, req: ContinueRequest, signal?: AbortSignal): Promise<void> {
  await request(`/api/chats/${chatId}/continue`, {
    method: "POST",
    body: req,
    signal,
  });
}

export async function rewindChat(chatId: string, req: RewindRequest, signal?: AbortSignal): Promise<ChatDetail> {
  return request<ChatDetail>(`/api/chats/${chatId}/rewind`, {
    method: "POST",
    body: req,
    signal,
  });
}

export async function updateChatSettings(chatId: string, req: UpdateChatSettingsRequest, signal?: AbortSignal): Promise<void> {
  await request(`/api/chats/${chatId}/settings`, {
    method: "PUT",
    body: req,
    signal,
  });
}

export async function archiveChat(chatId: string, signal?: AbortSignal): Promise<void> {
  await request(`/api/chats/${chatId}/archive`, { method: "PUT", signal });
}

export async function deleteChat(chatId: string, signal?: AbortSignal): Promise<void> {
  await request(`/api/chats/${chatId}`, { method: "DELETE", signal });
}

export async function listChatMemories(chatId: string, signal?: AbortSignal): Promise<ChatMemoryItem[]> {
  return request<ChatMemoryItem[]>(`/api/chats/${chatId}/memories`, { signal });
}

export async function deleteChatMemory(chatId: string, memoryId: string, signal?: AbortSignal): Promise<void> {
  await request(`/api/chats/${chatId}/memories/${memoryId}`, { method: "DELETE", signal });
}

export interface CompactSSEHandlers {
  onPhase?: (phase: string) => void;
  onToken?: (content: string) => void;
  onToolCallStart?: (toolName: string, args: Record<string, string>, stageName?: string) => void;
  onToolCallResult?: (toolName: string, result: string) => void;
  onDone?: (response: CompactResponse) => void;
  onError?: (detail: string) => void;
}

export function compactChatStream(
  chatId: string,
  req: CompactRequest,
  handlers: CompactSSEHandlers,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`/api/chats/${chatId}/compact`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(req),
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        handlers.onError?.(err.detail || res.statusText);
        return;
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop()!;

        for (const part of parts) {
          if (!part.trim()) continue;
          let eventType = "message";
          let data = "";
          for (const line of part.split("\n")) {
            if (line.startsWith("event: ")) eventType = line.slice(7).trim();
            else if (line.startsWith("data: ")) data = line.slice(6);
          }
          if (!data) continue;
          const parsed = JSON.parse(data) as Record<string, unknown>;
          switch (eventType) {
            case "phase":
              handlers.onPhase?.(parsed.phase as string);
              break;
            case "token":
              handlers.onToken?.(parsed.content as string);
              break;
            case "tool_call_start":
              handlers.onToolCallStart?.(
                parsed.tool_name as string,
                parsed.arguments as Record<string, string>,
                parsed.stage_name as string | undefined,
              );
              break;
            case "tool_call_result":
              handlers.onToolCallResult?.(parsed.tool_name as string, parsed.result as string);
              break;
            case "compact_done":
              handlers.onDone?.({
                summary: parsed.summary as ChatSummary,
                updated_message_count: parsed.updated_message_count as number,
              });
              break;
            case "error":
              handlers.onError?.(parsed.detail as string);
              break;
          }
        }
      }
    } catch (err) {
      if ((err as DOMException).name !== "AbortError") {
        handlers.onError?.(err instanceof Error ? err.message : "Stream failed");
      }
    }
  })();

  return controller;
}

export async function unsummarizeLast(chatId: string, summaryId: string, signal?: AbortSignal): Promise<ChatMessage[]> {
  return request<ChatMessage[]>(`/api/chats/${chatId}/summaries/${summaryId}`, {
    method: "DELETE",
    signal,
  });
}

export async function listSummaries(chatId: string, signal?: AbortSignal): Promise<ChatSummary[]> {
  return request<ChatSummary[]>(`/api/chats/${chatId}/summaries`, { signal });
}

export async function getOriginalMessages(chatId: string, summaryId: string, signal?: AbortSignal): Promise<ChatMessage[]> {
  return request<ChatMessage[]>(`/api/chats/${chatId}/summaries/${summaryId}/messages`, { signal });
}

export async function regenerateSummary(chatId: string, summaryId: string, signal?: AbortSignal): Promise<ChatSummary> {
  return request<ChatSummary>(`/api/chats/${chatId}/summaries/${summaryId}/regenerate`, {
    method: "POST",
    signal,
  });
}

function _streamChat(
  url: string,
  body: object | null,
  handlers: ChatSSEHandlers,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: authHeaders(),
        body: body !== null ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        handlers.onError?.(err.detail || res.statusText);
        return;
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop()!;

        for (const part of parts) {
          if (!part.trim()) continue;
          let eventType = "message";
          let data = "";
          for (const line of part.split("\n")) {
            if (line.startsWith("event: ")) eventType = line.slice(7).trim();
            else if (line.startsWith("data: ")) data = line.slice(6);
          }
          if (!data) continue;
          const parsed = JSON.parse(data) as Record<string, unknown>;
          switch (eventType) {
            case "token":
              handlers.onToken?.(parsed.content as string);
              break;
            case "thinking":
              console.debug("[SSE] thinking chunk", (parsed.content as string).length, "chars");
              handlers.onThinking?.(parsed.content as string);
              break;
            case "thinking_done":
              console.debug("[SSE] thinking_done");
              handlers.onThinkingDone?.();
              break;
            case "tool_call_start":
              console.debug("[SSE] tool_call_start:", parsed.tool_name, parsed.arguments);
              handlers.onToolCallStart?.(
                parsed.tool_name as string,
                parsed.arguments as Record<string, string>,
                parsed.stage_name as string | undefined,
              );
              break;
            case "tool_call_result":
              console.debug("[SSE] tool_call_result:", parsed.tool_name, parsed.result);
              handlers.onToolCallResult?.(parsed.tool_name as string, parsed.result as string);
              break;
            case "phase":
              console.debug("[SSE] phase:", parsed.phase);
              handlers.onPhase?.(parsed.phase as "planning" | "writing");
              break;
            case "status":
              console.debug("[SSE] status:", parsed.text);
              handlers.onStatus?.(parsed.text as string);
              break;
            case "stat_update":
              console.debug("[SSE] stat_update:", parsed);
              handlers.onStatUpdate?.({
                character_stats: parsed.character_stats as Record<string, number | string | string[]>,
                world_stats: parsed.world_stats as Record<string, number | string | string[]>,
                turn_number: parsed.turn_number as number,
              });
              break;
            case "variants_update":
              console.debug("[SSE] variants_update:", parsed.variants);
              handlers.onVariantsUpdate?.(parsed.variants as GenerationVariant[]);
              break;
            case "user_ack":
              console.debug("[SSE] user_ack:", parsed);
              handlers.onUserAck?.(parsed as { id: string; turn_number: number; created_at: string });
              break;
            case "done":
              console.debug("[SSE] done, message id:", (parsed.message as ChatMessage)?.id);
              handlers.onDone?.(parsed.message as ChatMessage);
              break;
            case "error":
              console.error("[SSE] error:", parsed.detail);
              handlers.onError?.(parsed.detail as string);
              break;
          }
        }
      }
    } catch (err) {
      if ((err as DOMException).name !== "AbortError") {
        handlers.onError?.(err instanceof Error ? err.message : "Stream failed");
      }
    }
  })();

  return controller;
}

export function sendMessage(
  chatId: string,
  req: SendMessageRequest,
  handlers: ChatSSEHandlers,
): AbortController {
  return _streamChat(`/api/chats/${chatId}/message`, req, handlers);
}

export function regenerateMessage(
  chatId: string,
  handlers: ChatSSEHandlers,
  turnNumber?: number,
): AbortController {
  const body = turnNumber != null ? { turn_number: turnNumber } : {};
  return _streamChat(`/api/chats/${chatId}/regenerate`, body, handlers);
}

export async function editMessage(chatId: string, messageId: string, content: string, signal?: AbortSignal): Promise<ChatDetail> {
  return request<ChatDetail>(`/api/chats/${chatId}/messages/${messageId}`, {
    method: "PUT",
    body: { content },
    signal,
  });
}

export async function deleteMessage(chatId: string, messageId: string, signal?: AbortSignal): Promise<ChatDetail> {
  return request<ChatDetail>(`/api/chats/${chatId}/messages/${messageId}`, {
    method: "DELETE",
    signal,
  });
}
