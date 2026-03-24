import type { TranslateRequest } from "../types/llmChat";
import type { TranslateStreamHandlers } from "../hooks/useTranslation";
import { authHeaders, authRequest } from "./request";
import { streamTranslate } from "./translateStream";

export interface ChatSSEHandlers {
  onToken?: (content: string) => void;
  onThinking?: (content: string) => void;
  onThinkingDone?: () => void;
  onToolCallStart?: (toolName: string, args: Record<string, string>) => void;
  onToolCallResult?: (toolName: string, result: string) => void;
  onPhase?: (phase: "planning" | "writing") => void;
  onStatus?: (text: string) => void;
  onStatUpdate?: (stats: Record<string, number | string | string[]>) => void;
  onUserAck?: (ack: { id: string; turn_number: number; created_at: string }) => void;
  onDone?: (message: ChatMessage) => void;
  onError?: (detail: string) => void;
}

export function translateTextChat(req: TranslateRequest, handlers: TranslateStreamHandlers): AbortController {
  return streamTranslate("/api/chats/translate", req, handlers);
}

export async function listPublicWorlds(): Promise<WorldInfo[]> {
  return authRequest<WorldInfo[]>("/api/chats/worlds");
}

export async function createChat(req: CreateChatRequest): Promise<ChatSession> {
  return authRequest<ChatSession>("/api/chats", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function listMyChats(): Promise<ChatSessionItem[]> {
  const res = await authRequest<{ items: ChatSessionItem[] }>("/api/chats");
  return res.items;
}

export async function getChatDetail(chatId: string): Promise<ChatDetail> {
  return authRequest<ChatDetail>(`/api/chats/${chatId}`);
}

export async function continueChat(chatId: string, req: ContinueRequest): Promise<void> {
  await authRequest(`/api/chats/${chatId}/continue`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function rewindChat(chatId: string, req: RewindRequest): Promise<ChatDetail> {
  return authRequest<ChatDetail>(`/api/chats/${chatId}/rewind`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function updateChatSettings(chatId: string, req: UpdateChatSettingsRequest): Promise<void> {
  await authRequest(`/api/chats/${chatId}/settings`, {
    method: "PUT",
    body: JSON.stringify(req),
  });
}

export async function archiveChat(chatId: string): Promise<void> {
  await authRequest(`/api/chats/${chatId}/archive`, { method: "PUT" });
}

export async function deleteChat(chatId: string): Promise<void> {
  await authRequest(`/api/chats/${chatId}`, { method: "DELETE" });
}

export async function listChatMemories(chatId: string): Promise<ChatMemoryItem[]> {
  return authRequest<ChatMemoryItem[]>(`/api/chats/${chatId}/memories`);
}

export async function deleteChatMemory(chatId: string, memoryId: string): Promise<void> {
  await authRequest(`/api/chats/${chatId}/memories/${memoryId}`, { method: "DELETE" });
}

export async function compactChat(chatId: string, req: CompactRequest): Promise<CompactResponse> {
  return authRequest<CompactResponse>(`/api/chats/${chatId}/compact`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function listSummaries(chatId: string): Promise<ChatSummary[]> {
  return authRequest<ChatSummary[]>(`/api/chats/${chatId}/summaries`);
}

export async function getOriginalMessages(chatId: string, summaryId: string): Promise<ChatMessage[]> {
  return authRequest<ChatMessage[]>(`/api/chats/${chatId}/summaries/${summaryId}/messages`);
}

export async function regenerateSummary(chatId: string, summaryId: string): Promise<ChatSummary> {
  return authRequest<ChatSummary>(`/api/chats/${chatId}/summaries/${summaryId}/regenerate`, {
    method: "POST",
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
              console.debug("[SSE] stat_update:", parsed.stats);
              handlers.onStatUpdate?.(parsed.stats as Record<string, number | string | string[]>);
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

export async function editMessage(chatId: string, messageId: string, content: string): Promise<ChatDetail> {
  return authRequest<ChatDetail>(`/api/chats/${chatId}/messages/${messageId}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

export async function deleteMessage(chatId: string, messageId: string): Promise<ChatDetail> {
  return authRequest<ChatDetail>(`/api/chats/${chatId}/messages/${messageId}`, {
    method: "DELETE",
  });
}
