import type { LlmChatRequest, SSEHandlers, TranslateRequest, TranslateResponse } from "../types/llmChat";
import type { EnabledModelInfo, EnabledModelsListResponse } from "../types/llmServer";
import { authRequest } from "./request";
import { streamPost } from "./sse";

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

export async function translateTextAdmin(req: TranslateRequest): Promise<TranslateResponse> {
  return authRequest<TranslateResponse>("/api/llm/translate", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
