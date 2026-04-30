# Stage 1 Step 7 — Admin LLM Tools

## What Was Built

Three MCP-style tools available exclusively to admin/editor users during LLM-assisted document editing:

- **search(query, source_type?)** — Semantic vector search across world documents (locations, NPCs, lore facts). Deduplicates results by source document, fetches full text, returns top-5 joined by `---`.
- **get_lore(query)** — Same as search but scoped to `lore_fact` type, returns single best match. Designed for targeted consistency lookups.
- **web_search(query)** — Google Custom Search API. Reads `SEARCH_CSE_KEY` and `SEARCH_CSE_ID` from env at call time. Returns 5 results formatted as title/URL/snippet.

Tools are wired via `POST /api/llm/chat` when `enable_tools: true` in the request. The agentic loop runs up to **15 rounds** to allow thorough multi-step research before writing.

## Key Design Decisions

**Lore strategy when tools are enabled.** Non-injected lore facts are not included in context — the LLM fetches them actively via `search`/`get_lore`. However, `is_injected=True` lore facts are always present (see stage1_step7b). Rationale: injecting all lore creates a huge, mostly irrelevant context blob; active fetching forces the LLM to be deliberate and produces better consistency checks.

**Tool call SSE events during agentic loop.** Each tool invocation emits `tool_call_start` (with name + arguments) and `tool_call_result` (with returned string) as SSE events before the final answer streams. This gives the frontend real-time visibility into what the LLM is researching.

**`functools.wraps` on tool wrappers is required.** Tool callables are wrapped in closures that emit SSE events around the actual call. The wrapper must carry `@functools.wraps(impl)` so that `inspect.signature()` follows `__wrapped__` to the original function's parameter spec — `chat_with_tools` uses this to validate arguments. Without the decorator, every tool call fails validation.

**Streaming added to tools mode (llm-client 0.1.3).** Initial implementation emitted the full final answer as a single `token` event. After the llm-client gained `stream=True` + `on_delta` support, this was updated to stream tokens in real-time via the same `on_delta` callback as plain chat mode.

## Files

- `backend/app/services/admin_tools.py` — tool schemas (Pydantic), implementations, `get_admin_tools(world_id)` factory
- `backend/app/routes/llm_chat.py` — `_run_with_tools()` helper, branching on `enable_tools`
- `backend/app/models/schemas/llm_chat.py` — `enable_tools: bool` field on `LlmChatRequest`
- `backend/app/services/prompts/document_editor_system_prompt.py` — lore injection skipped when tools enabled; tool usage strategy section appended
- `frontend/src/types/llmChat.d.ts` — `ToolCallEntry`, `onToolCallStart`/`onToolCallResult` handlers, `toolCalls` on `ChatMessage`
- `frontend/src/api/sse.ts` — `tool_call_start` / `tool_call_result` event dispatch
- `frontend/src/admin/components/LlmChatPanel.tsx` — tools toggle, `ToolCallRow` component, per-message regenerate button
