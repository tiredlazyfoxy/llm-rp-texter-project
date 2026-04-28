import type { LlmChatRequest, SSEHandlers, TranslateRequest } from "../types/llmChat";
import type { EnabledModelInfo, EnabledModelsListResponse } from "../types/llmServer";
import type { TranslateStreamHandlers } from "../hooks/useTranslation";
import { authRequest } from "./request";
import { streamPost } from "./sse";
import { streamTranslate } from "./translateStream";

export function streamChat(
  request: LlmChatRequest,
  handlers: SSEHandlers,
): AbortController {
  return streamPost("/api/llm/chat", request, handlers);
}

export async function fetchEnabledModels(): Promise<EnabledModelInfo[]> {
  const res = await authRequest<EnabledModelsListResponse>("/api/llm/models");
  return res.models;
}

export function translateTextAdmin(req: TranslateRequest, handlers: TranslateStreamHandlers): AbortController {
  return streamTranslate("/api/llm/translate", req, handlers);
}
