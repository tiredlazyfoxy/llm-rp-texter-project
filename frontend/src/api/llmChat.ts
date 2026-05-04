import type { LlmChatRequest, SSEHandlers, TranslateRequest } from "../types/llmChat";
import type { EnabledModelInfo, EnabledModelsListResponse } from "../types/llmServer";
import type { TranslateStreamHandlers } from "../hooks/useTranslation";
import { request } from "./client";
import { streamPost } from "./sse";
import { streamTranslate } from "./translateStream";

export function streamChat(
  req: LlmChatRequest,
  handlers: SSEHandlers,
): AbortController {
  return streamPost("/api/llm/chat", req, handlers);
}

export async function fetchEnabledModels(signal?: AbortSignal): Promise<EnabledModelInfo[]> {
  const res = await request<EnabledModelsListResponse>("/api/llm/models", { signal });
  return res.models;
}

export function translateTextAdmin(req: TranslateRequest, handlers: TranslateStreamHandlers): AbortController {
  return streamTranslate("/api/llm/translate", req, handlers);
}
