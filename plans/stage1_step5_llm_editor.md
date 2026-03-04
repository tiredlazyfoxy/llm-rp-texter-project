# Stage 1 Step 5 — LLM-Assisted Document Editor

## Context

After the world editor (step 4) provides a plain text editor for documents, this step adds LLM-assisted editing to the Document Edit page. Based on the reference implementation from DatasetControlCenter (`PromptEditorPanel.tsx` + `llm_chat.py`), adapted for world document editing (locations, NPCs, lore facts).

Adds a chat panel below the text editor where editors discuss edits with an LLM. The LLM receives current document content + world context and generates text that can be applied to or appended to the document.

---

## 1. Backend — LLM Chat Service

**File**: `backend/app/services/llm_chat.py`

### `get_llm_client_for_model(model_id: str, db: Session)`

- Query active LLM servers (`is_active=True`)
- Parse each server's `enabled_models` JSON array
- Find first server with `model_id` enabled
- Resolve `$ENV_VAR` api key if present
- Instantiate `LlamaSwapAPIClient` or `OpenAIAPIClient` based on `backend_type`
- Raise `ValueError` if no server has this model

### `build_document_editor_system(doc_type, world_name, world_description, world_lore, current_content) -> str`

Builds system prompt for document editing context:
- Task: "Assisting an editor writing/editing a {doc_type} document for the RPG world '{world_name}'"
- World description and lore as background context
- Current document content included
- Instructions: respond with edited text in markdown, suitable for direct application

---

## 2. Backend — LLM Chat Route (SSE Streaming)

**File**: `backend/app/routes/llm_chat.py`

### Endpoint: `POST /api/llm/chat`

Role: **editor**

### Pydantic Schemas

```python
class ChatMessageIn(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class LlmChatRequest(BaseModel):
    model_id: str
    messages: list[ChatMessageIn]
    temperature: float = 0.7
    top_p: float = 1.0
    repetition_penalty: float = 1.0
    enable_thinking: bool = False
    current_content: str      # current document text
    world_id: str             # snowflake as string
    doc_id: str               # snowflake as string
    doc_type: str             # "location" | "npc" | "lore_fact"
```

### SSE Event Format

| Event | Data | Purpose |
|---|---|---|
| `token` | `{"content": "..."}` | Content token delta |
| `thinking` | `{"content": "..."}` | Thinking content delta |
| `thinking_done` | `{}` | Thinking phase complete |
| `done` | `{"content": "...full..."}` | Complete response |
| `error` | `{"message": "..."}` | Error |

### Flow

1. Parse request, load world from DB by `world_id` (name, description, lore for system prompt)
2. Build system prompt via `build_document_editor_system()`
3. Get LLM client via `get_llm_client_for_model()`
4. Stream LLM response as SSE:
   - Detect `<think>...</think>` tags → separate into `thinking` events
   - Content outside tags → `token` events
   - On `</think>` → `thinking_done` event
   - On completion → `done` event with full accumulated content (thinking stripped)
   - On error → `error` event
5. Return `StreamingResponse` with `text/event-stream` content type

### SSE wire format

```
event: token
data: {"content": "Hello"}

event: done
data: {"content": "Hello world, this is the full response."}

```

### Mount

Add to `backend/app/main.py`:
```python
from app.routes.llm_chat import router as llm_chat_router
app.include_router(llm_chat_router)
```

---

## 3. Frontend — SSE Streaming Utility

**File**: `frontend/src/api/sse.ts`

### `streamPost(url, body, handlers): AbortController`

- POST to URL with JSON body + JWT Authorization header
- Read response as `ReadableStream`
- Parse SSE events (split by `\n\n`, extract `event:` and `data:` lines)
- Dispatch to handler callbacks based on event type
- Return `AbortController` for cancellation

### SSEHandlers interface

```typescript
interface SSEHandlers {
  onToken?: (content: string) => void;
  onThinking?: (content: string) => void;
  onThinkingDone?: () => void;
  onDone?: (content: string) => void;
  onError?: (message: string) => void;
}
```

---

## 4. Frontend — Chat API Client

**File**: `frontend/src/api/llmChat.ts`

- `streamChat(request, handlers): AbortController` — wraps `streamPost("/api/llm/chat", ...)`
- `fetchEnabledModels(): Promise<EnabledModelInfo[]>` — `GET /api/llm/models` (from step 3)

---

## 5. Frontend — TypeScript Types

**File**: `frontend/src/types/llmChat.d.ts`

```typescript
interface ChatMessageIn {
  role: "user" | "assistant";
  content: string;
}

interface LlmChatRequest {
  model_id: string;
  messages: ChatMessageIn[];
  temperature: number;
  top_p: number;
  repetition_penalty: number;
  enable_thinking: boolean;
  current_content: string;
  world_id: string;
  doc_id: string;
  doc_type: "location" | "npc" | "lore_fact";
}

interface SSEHandlers {
  onToken?: (content: string) => void;
  onThinking?: (content: string) => void;
  onThinkingDone?: () => void;
  onDone?: (content: string) => void;
  onError?: (message: string) => void;
}

interface ChatMessage {
  id: string;           // client-generated UUID for React keys
  role: "user" | "assistant";
  content: string;
  thinkingContent?: string;
  isStreaming?: boolean;
}

interface EditorLlmParams {
  temperature: number;
  top_p: number;
  repetition_penalty: number;
  enable_thinking: boolean;
}
```

---

## 6. Frontend — LlmChatPanel Component

**File**: `frontend/src/admin/components/LlmChatPanel.tsx`
**UI Library**: Mantine

### Props

```typescript
interface LlmChatPanelProps {
  currentContent: string;
  worldId: string;
  docId: string;
  docType: "location" | "npc" | "lore_fact";
  onApply: (content: string) => void;   // replace document content
  onAppend: (content: string) => void;  // append to document content
}
```

### UI Layout

**Top bar**: Model dropdown (loads from `fetchEnabledModels()`, persists in localStorage key `llmrp_editor_model`) + "Clear Chat" button

**Parameters** (collapsible section, all persist in localStorage key `llmrp_editor_params` as JSON):
- Temperature slider (0–2, step 0.1, default 0.7)
- Top-p slider (0–1, step 0.05, default 1.0)
- Repetition penalty slider (1.0–2.0, step 0.05, default 1.0)
- Thinking mode switch

**Chat messages** (scrollable, auto-scroll on new content):
- User messages: simple text
- Assistant messages:
  - Thinking content in collapsible section (italic/dimmed)
  - Main content as text
  - Action buttons: **Apply** (`onApply`), **Append** (`onAppend`), **Delete** (remove from chat)
- Streaming indicator: blinking cursor / spinner after last token

**Input area** (bottom):
- Textarea (Shift+Enter for newlines, Enter to send)
- Send button (disabled while streaming)
- Stop button (visible while streaming, calls `AbortController.abort()`)
- Regenerate button on last assistant message

### Chat Flow

1. User sends message → add to messages array
2. Build `LlmChatRequest` with current params, model, all messages, `currentContent` from props
3. Add empty assistant message with `isStreaming: true`
4. Call `streamChat()` — handlers update assistant message incrementally
5. On `done` → mark `isStreaming: false`, set final content

### Actions

- **Apply**: calls `props.onApply(content)` — parent replaces document content
- **Append**: calls `props.onAppend(content)` — parent appends to document content
- **Delete message**: removes from array
- **Regenerate**: remove last assistant message, re-send
- **Clear chat**: empty messages array
- **Stop**: `abortController.abort()`, keep partial content

---

## 7. DocumentEdit Modification

**File**: `frontend/src/admin/pages/DocumentEdit.tsx` (from step 4)

Add `LlmChatPanel` below the text editor:
- Pass `currentContent` (textarea value), `worldId`, `docId`, `docType`
- `onApply` → set textarea content
- `onAppend` → append to textarea content

Layout:
```
+----------------------------------+
|  Name field                      |
|  Type indicator                  |
|  Content textarea (markdown)     |
|  Exits / NPC location links      |
|  [Save button]                   |
+----------------------------------+
|  LLM Chat Panel                  |
|  (model selector, params,        |
|   messages, input)               |
+----------------------------------+
```

---

## File Summary

### New Files

| File | Purpose |
|---|---|
| `backend/app/services/llm_chat.py` | LLM client factory + system prompt builder |
| `backend/app/routes/llm_chat.py` | SSE streaming chat endpoint |
| `frontend/src/api/sse.ts` | Generic SSE streaming utility |
| `frontend/src/api/llmChat.ts` | Chat API client |
| `frontend/src/types/llmChat.d.ts` | TypeScript types |
| `frontend/src/admin/components/LlmChatPanel.tsx` | Reusable LLM chat panel |

### Modified Files

| File | Change |
|---|---|
| `backend/app/main.py` | Mount `llm_chat` router |
| `frontend/src/admin/pages/DocumentEdit.tsx` | Add LlmChatPanel below text editor |

---

## Role Permissions

| Action | Required Role |
|---|---|
| Use LLM chat in document editor | editor |

---

## Dependencies

- Step 3 complete (LLM server management, `/api/llm/models` endpoint)
- Step 4 complete (DocumentEdit page with plain text editor)
- PythonLLMClient streaming support

---

## Verification

1. Configure LLM server with enabled models (step 3)
2. Navigate to document edit page → chat panel visible below text editor
3. Select model, send message → SSE streaming tokens appear incrementally
4. Test **Apply** → document content replaced
5. Test **Append** → text appended to document
6. Test **Stop** during streaming → partial content retained
7. Test **Delete / Regenerate / Clear Chat**
8. Toggle thinking mode → `<think>` tags parsed, shown in collapsible section
9. Adjust params → verify localStorage persistence across page reload
10. Verify model selection persists in localStorage
