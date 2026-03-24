import type { TranslateRequest } from "../types/llmChat";
import type { TranslateStreamHandlers } from "../hooks/useTranslation";
import { authHeaders } from "./request";

export function streamTranslate(
  url: string,
  req: TranslateRequest,
  handlers: TranslateStreamHandlers,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(req),
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        handlers.onError(err.detail || err.message || res.statusText);
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

          const parsed = JSON.parse(data) as Record<string, string>;
          switch (eventType) {
            case "thinking":
              handlers.onThinking(parsed.content);
              break;
            case "token":
              handlers.onToken(parsed.content);
              break;
            case "done":
              handlers.onDone(parsed.content);
              break;
            case "error":
              handlers.onError(parsed.message);
              break;
          }
        }
      }
    } catch (err) {
      if ((err as DOMException).name !== "AbortError") {
        handlers.onError(err instanceof Error ? err.message : "Stream failed");
      }
    }
  })();

  return controller;
}
