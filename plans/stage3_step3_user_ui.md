# Stage 3 Step 3 — User Chat UI + Debug Mode + Message Management

## Context

Step 2 implements the backend for all generation modes (simple with tools, chain pipeline, future agentic). Step 3 adapts the user-facing frontend to work with all modes and adds: debug mode for editors, enhanced message management (edit, delete, re-send), flexible summarization, and pipeline-aware status display.

### Key Convention

**User Instructions** (`session.user_instructions`) — the player's recommendations/feedback about RP flow — must always be included in all prompts across all generation modes. The ChatSettingsPanel textarea for user instructions is kept as-is. This field is injected into every system prompt (simple, chain planning, chain writing) as a "Player Instructions" section.

### Dependencies

- Stage 3 Step 1 (generation_mode, PipelineConfig, hidden stats)
- Stage 3 Step 2a (simple mode with tools, rich prompt, SSE status events)
- Stage 3 Step 2b (chain mode, SSE phase/status events, generation_plan on messages)

---

## 1. Debug Mode

### 1a. Concept

A toggle switch available to **editors and admins** (not regular players). Controls how much detail is shown during and after generation.

**Normal mode** (all users):

- Brief status text during generation: "Searching for lore fact — weather behaviour", "Calling sub-agent planning for turn resolution"
- No raw data, no tool arguments/results, no thinking content
- Clean message bubbles with just the narrative prose

**Debug mode** (editors/admins only):

- Collapsible panels with full data sent to/from tools, agents, stages
- Tool calls: full arguments + full result text (collapsible, no truncation)
- Thinking content: full LLM reasoning (collapsible)
- Generation plan (chain mode): collected_data, decisions, stat_updates (collapsible)
- Phase transitions visible
- Hidden stats visible (with "hidden" indicator)

### 1b. Backend SSE Support

**New SSE event types** (emitted by all generation modes):

| Event | Data | When |
| ---- | ---- | ---- |
| `phase` | `{"phase": "planning" \| "writing"}` | Stage transitions in chain mode |
| `status` | `{"text": "Searching for..."}` | Human-readable status at key points |

**Existing events already carry debug info**:

- `tool_call_start` — `{"tool_name": "...", "arguments": {...}}` — full arguments
- `tool_call_result` — `{"tool_name": "...", "result": "..."}` — full result
- `thinking` — `{"content": "..."}` — reasoning content

**Backend filtering** (already designed in step 2):

- **Players**: receive `status`, `phase`, `token`, `stat_update`, `done`, `error` only
- **Editors+**: receive ALL events including `thinking`, `tool_call_start`, `tool_call_result`

The filtering happens server-side based on `caller_role`. Frontend just needs to decide what to render based on the debug toggle — if events arrive, they're available; if filtered by backend, they simply don't arrive.

**Status event generation points**:

- Simple mode: "Calling tool: {tool_name}...", "Processing response..."
- Chain planning: "Gathering context...", "Planning response..."
- Chain writing: "Writing..."
- Tool calls: "Searching for: {query}", "Looking up location: {name}"

### 1c. Frontend — Debug Toggle State

**`frontend/src/user/stores/ChatStore.ts`** — add:

```typescript
// Observables
debugMode: boolean = false           // persisted to localStorage per session
currentPhase: "planning" | "writing" | null = null
currentStatus: string | null = null

// Actions
toggleDebugMode(): void              // flip + persist to localStorage
```

Debug mode is per-user preference, stored in `localStorage` (key: `chatDebugMode`). Loaded on store init.

### 1d. Frontend — Settings Panel Toggle

**`frontend/src/user/components/ChatSettingsPanel.tsx`** — add at bottom of drawer:

- Only visible when user role is `editor` or `admin` (check from auth context / session info)
- `Switch` component: "Debug mode — Show detailed generation info"
- Bound to `chatStore.debugMode` / `chatStore.toggleDebugMode()`

### 1e. Frontend — Status Display During Generation

**`frontend/src/user/components/ChatInput.tsx`** — when `isSending === true`:

- If `currentStatus` is non-null: show animated status text below the input area
- Pulsing dot or spinner + status text (e.g., "⏳ Gathering context...")
- If `currentPhase` is set: optionally show phase badge (e.g., `[Planning]` or `[Writing]`)
- Falls back to existing loading indicator when no status text

### 1f. Frontend — SSE Handler Additions

**`frontend/src/api/chat.ts`** — add to `_streamChat()` event parser:

```typescript
case "phase":
  handlers.onPhase?.(parsed.phase);
  break;
case "status":
  handlers.onStatus?.(parsed.text);
  break;
```

**`ChatSSEHandlers`** interface — add:

```typescript
onPhase?: (phase: "planning" | "writing") => void;
onStatus?: (text: string) => void;
```

**`ChatStore.ts`** — wire in `sendMessage()` and `regenerate()`:

```typescript
onPhase: action((phase) => { this.currentPhase = phase; }),
onStatus: action((text) => { this.currentStatus = text; }),
```

On `done` callback: reset `currentPhase = null`, `currentStatus = null`.

### 1g. Frontend — Debug Panels on Message Bubbles

**`frontend/src/user/components/MessageBubble.tsx`** — for assistant messages:

**When debug mode OFF**: render message content only (current behavior, clean)

**When debug mode ON** (and data available):

1. **Tool Calls** — enhance existing `ToolCallTrace`:
   - Remove 200-char truncation on result text
   - Show arguments as formatted/indented JSON
   - Each tool call collapsible individually
   - Show full result in scrollable monospace area

2. **Thinking** — collapsible "Thinking" section:
   - For streaming: already shows thinking (keep as-is)
   - For loaded messages: need to store thinking content on message (see §1h)
   - Collapsed by default, monospace text

3. **Generation Plan** (chain mode, `message.generation_plan` is non-null):
   - Collapsible "Generation Plan" section
   - Sub-sections:
     - **Collected Data**: formatted text block
     - **Decisions**: bullet list
     - **Stat Updates**: simple table (name → value)

4. **Phase Info** (nice-to-have):
   - Small badge showing which mode generated this message (simple/chain)

### 1h. Storing Debug Data on Messages

Currently, thinking content is only streamed — not stored on the message after generation. For debug mode to work on already-loaded messages, we need to store it.

**Option A** (recommended): Store thinking content in `tool_calls` or a new field on ChatMessage. Since `generation_plan` already stores chain mode data, we could add `thinking_content: str | null` to ChatMessage.

**Option B**: Only show debug panels for streaming messages (not loaded ones). Simpler but less useful.

Recommendation: **Option A** — add `thinking_content` column to ChatMessage. Backend saves it during generation. Import/export updated.

### 1i. Hidden Stats in Debug Mode

**`frontend/src/user/components/StatsPanel.tsx`**:

- Default: filter out stats where matching `StatDefinition.hidden === true`
- When `chatStore.debugMode === true` AND user is editor+:
  - Show all stats including hidden ones
  - Hidden stats rendered with dimmed opacity or a small "hidden" badge
- Stat definitions available from world info (already loaded in chat detail via `publicWorlds`)

---

## 2. Message Management

### 2a. Edit User Message + Re-send

Allow editing any **non-summarized** user message and re-generating from that point.

**UI (MessageBubble.tsx)** — on user message bubbles (non-summarized, non-system):

- Small "Edit" icon button (pencil icon) on hover/focus
- Clicking edit: message content replaced with inline `Textarea` (pre-filled with current content)
- Two buttons below textarea: "Save & Resend" (primary) + "Cancel" (subtle)
- "Save & Resend" calls store action → API → triggers re-generation

**Backend — New Endpoint**:

```
PUT /api/chats/{chat_id}/messages/{message_id}
Body: { "content": "updated text" }
Response: ChatDetailResponse
```

**Backend Flow** (`chat_service.py` → `edit_and_resend()`):

1. Validate: message exists, belongs to session, is user role, is non-summarized
2. Update message content in DB
3. Delete all messages AFTER this message's turn_number (assistant at same turn + all future turns)
4. Delete snapshots after this turn's user message (keep snapshot at turn before)
5. Delete summaries that overlap with deleted range
6. Restore session state from snapshot at previous turn (turn_number - 1)
7. Set session `current_turn` to this message's `turn_number - 1` (so the next send increments to the right turn)
8. Return updated `ChatDetailResponse`

After the API returns, the frontend automatically calls `sendMessage()` with the updated content to generate a new assistant response.

**DB layer** (`db/chats.py`):

- `update_message_content(message_id: int, content: str)` — update content field only
- Reuse existing: `delete_messages_after_turn()`, `delete_snapshots_after_turn()`, `delete_summaries_after_turn()`

### 2b. Delete Messages

Allow deleting **non-summarized** messages (both user and assistant, not system).

**UI (MessageBubble.tsx)**:

- Small "Delete" icon button (trash icon) on hover/focus
- Only on non-summarized, non-system messages
- Click → confirmation modal ("Delete this message?")
- On confirm → calls store action → API

**Backend — New Endpoint**:

```
DELETE /api/chats/{chat_id}/messages/{message_id}
Response: ChatDetailResponse
```

**Backend Flow** (`chat_service.py` → `delete_message()`):

1. Validate: message exists, belongs to session, is non-summarized, is not system role
2. **If deleting a message at the current (latest) turn**:
   - If user message: delete user message + all assistant messages at same turn + snapshot at this turn
   - If assistant message: just mark inactive (or delete if no other variants)
   - Decrement `current_turn` if entire turn is removed
   - Restore stats from previous snapshot
3. **If deleting a message at a past turn**:
   - This is equivalent to rewind-to-turn-before + skip that turn
   - Simplest approach: delete all messages from this turn onwards, rewind to turn before
   - Return updated `ChatDetailResponse`

### 2c. Regenerate Any Turn

Current: regenerate button only works for the latest turn.

Enhancement: allow regenerating any **non-summarized** assistant message.

**UI (MessageBubble.tsx)** — on non-summarized assistant messages:

- "Regenerate" icon button (refresh icon)
- If this is the latest turn: calls existing `chatStore.regenerate()`
- If this is a past turn: calls new `chatStore.regenerateAtTurn(turnNumber)`

**Backend — Enhanced Endpoint**:

```
POST /api/chats/{chat_id}/regenerate
Body: { "turn_number": 5 }  // optional, defaults to current_turn
Response: StreamingResponse (SSE)
```

**Backend Flow**:

- If `turn_number` < `current_turn`: rewind to `turn_number` first, then regenerate
- If `turn_number` == `current_turn`: existing regenerate behavior
- This combines rewind + regenerate into a single operation

---

## 3. Summarization Enhancements

### 3a. Flexible Summarization Target

Current behavior: "Summarize up to here" button on assistant messages from previous turns. Summarizes from start (or last summary end) to that message.

Enhancement: Allow picking ANY non-summarized assistant message as the summarization target, even if there are non-summarized messages after it. Messages after the target remain non-summarized.

**UI (MessageHistory.tsx)**:

- "Summarize up to here" button — already exists on assistant messages from previous turns (not current turn)
- Keep as-is — the button already appears correctly
- Verify: clicking it on a message that's NOT adjacent to the last summary still works (there may be a gap)

**Backend verification**: `compact_messages()` in `summarization_service.py`:

- Currently: finds start point (after last summary or session start), gathers messages in range to target
- Need to verify: if target message has non-summarized messages before it that are NOT adjacent to last summary, those get included
- The logic should work: it finds all active non-summarized messages between start and target, summarizes them all

### 3b. Unwrap Summary (Existing — Verify)

`expandSummary(summaryId)` → `getOriginalMessages(chatId, summaryId)` → shows original messages inline.

**Verify**:

- Summary header shows with expand/collapse toggle
- Expanded messages render correctly with turn dividers
- Can collapse back to summary view

### 3c. Re-summarize (Existing — Verify)

`regenerateSummary(summaryId)` → `regenerateSummary(chatId, summaryId)` API call → LLM re-generates summary.

**Verify**:

- Works after expanding a summary
- Summary content updates in UI
- Loading state shown during regeneration

### 3d. Delete Summary / Permanent Unwrap (Existing — Verify)

`deleteMemory(memoryId)` → deletes summary, sets `summary_id = NULL` on linked messages.

**Verify**:

- Messages reappear in regular message flow
- No orphaned data
- UI updates correctly (summary disappears, messages become visible)

---

## 4. TypeScript Type Updates

### 4a. `frontend/src/types/chat.d.ts`

New/updated types:

```typescript
// Add to ChatMessage
generation_plan: string | null;       // JSON string of GenerationPlanOutput (chain mode)
thinking_content: string | null;      // stored thinking/reasoning content

// Add to WorldInfo (generation_mode is on World, not session)
generation_mode: "simple" | "chain" | "agentic";

// New SSE event interfaces
interface SSEPhaseEvent {
    phase: "planning" | "writing";
}

interface SSEStatusEvent {
    text: string;
}

// Add to StatDefinition
hidden: boolean;

// New request types
interface EditMessageRequest {
    content: string;
}

interface RegenerateRequest {
    turn_number?: number;             // optional, defaults to current_turn
}
```

### 4b. `frontend/src/api/chat.ts`

New API functions:

```typescript
editMessage(chatId: string, messageId: string, req: EditMessageRequest): Promise<ChatDetail>
deleteMessage(chatId: string, messageId: string): Promise<ChatDetail>
```

Update `ChatSSEHandlers`:

```typescript
onPhase?: (phase: "planning" | "writing") => void;
onStatus?: (text: string) => void;
```

Update `regenerateMessage()` to accept optional `turn_number` parameter.

---

## 5. Backend Changes

### 5a. New Endpoints — `backend/app/routes/chat.py`

```python
@router.put("/{chat_id}/messages/{message_id}")
async def edit_message(chat_id: str, message_id: str, req: EditMessageRequest, caller = Depends(_require_player)):
    detail = await chat_service.edit_message(int(chat_id), int(message_id), req.content, caller.id)
    return detail

@router.delete("/{chat_id}/messages/{message_id}")
async def delete_message(chat_id: str, message_id: str, caller = Depends(_require_player)):
    detail = await chat_service.delete_message(int(chat_id), int(message_id), caller.id)
    return detail
```

### 5b. New Request Schema — `backend/app/models/schemas/chat.py`

```python
class EditMessageRequest(BaseModel):
    content: str

class RegenerateRequest(BaseModel):
    turn_number: int | None = None
```

Update `ChatMessageResponse` — add `generation_plan: str | None`, `thinking_content: str | None`.

Update `WorldInfoResponse` — add `generation_mode: str` (frontend needs this to know which UI to show; `generation_mode` lives on World, not on ChatSession).

### 5c. Service Functions — `backend/app/services/chat_service.py`

```python
async def edit_message(session_id: int, message_id: int, new_content: str, user_id: int) -> ChatDetailResponse:
    """Edit user message content and delete all subsequent messages/snapshots."""

async def delete_message(session_id: int, message_id: int, user_id: int) -> ChatDetailResponse:
    """Delete a non-summarized message and adjust session state."""
```

### 5d. DB Layer — `backend/app/db/chats.py`

```python
async def update_message_content(message_id: int, content: str) -> None:
    """Update only the content field of a message."""
```

### 5e. ChatMessage Model — `backend/app/models/chat_message.py`

Add column:

```python
thinking_content: str | None = Field(default=None)
```

### 5f. Import/Export — `backend/app/services/db_import_export.py`

Add `thinking_content` to ChatMessage serialization (backward-compatible: default None).

### 5g. Generation Services — Emit Status Events

All generation services (`simple_generation_service.py`, `chain_generation_service.py`) must emit `status` SSE events at key points:

- Before tool calls: `status("Searching for: {query}")`
- Before planning: `status("Planning response...")`
- Before writing: `status("Writing...")`
- These are always emitted (not filtered by role)

Also save `thinking_content` on the assistant message after generation completes.

---

## 6. Files Summary

### Backend — Modify

| File | Change |
| ---- | ---- |
| `backend/app/routes/chat.py` | New PUT/DELETE message endpoints, optional turn_number on regenerate |
| `backend/app/models/schemas/chat.py` | EditMessageRequest, RegenerateRequest, generation_plan + thinking_content on message |
| `backend/app/services/chat_service.py` | `edit_message()`, `delete_message()` |
| `backend/app/db/chats.py` | `update_message_content()` |
| `backend/app/models/chat_message.py` | Add `thinking_content` column |
| `backend/app/services/db_import_export.py` | Add `thinking_content` to ChatMessage |
| `backend/app/services/simple_generation_service.py` | Emit `status` events, save `thinking_content` |
| `backend/app/services/chain_generation_service.py` | Emit `status` events, save `thinking_content` |
| `backend/app/services/chat_agent_service.py` | Pass turn_number to regenerate dispatch |

### Frontend — Modify

| File | Change |
| ---- | ---- |
| `frontend/src/types/chat.d.ts` | generation_plan, thinking_content on ChatMessage; generation_mode on WorldInfo; hidden on StatDefinition; SSE phase/status types; EditMessageRequest, RegenerateRequest |
| `frontend/src/api/chat.ts` | editMessage(), deleteMessage(), onPhase/onStatus SSE handlers, regenerate with turn_number |
| `frontend/src/user/stores/ChatStore.ts` | debugMode, currentPhase, currentStatus, toggleDebugMode, editMessage, deleteMessage, regenerateAtTurn |
| `frontend/src/user/components/ChatInput.tsx` | Status indicator with animated text during generation |
| `frontend/src/user/components/MessageBubble.tsx` | Debug panels (generation plan, thinking, enhanced tool calls), edit/delete/regenerate action buttons |
| `frontend/src/user/components/ChatSettingsPanel.tsx` | Debug mode toggle switch (editor+ only) |
| `frontend/src/user/components/StatsPanel.tsx` | Hidden stat filtering + debug mode reveal |
| `frontend/src/user/components/ToolCallTrace.tsx` | Remove 200-char truncation in debug mode, formatted JSON args |
| `frontend/src/user/components/MessageHistory.tsx` | Inline edit textarea for user messages |

---

## 7. Verification

1. **Debug toggle**: visible only for editor+ users in settings drawer, persists to localStorage
2. **Debug OFF**: clean messages, brief status text during generation, no tool/thinking/plan details
3. **Debug ON**: collapsible panels for tool calls (full args + results), thinking content, generation plan (chain mode)
4. **Hidden stats**: filtered in StatsPanel normally, visible with badge in debug mode (editor+ only)
5. **Status indicator**: animated status text during generation ("Gathering context...", "Writing...")
6. **Phase display**: currentPhase updates through planning → writing in chain mode
7. **Edit message**: pencil icon on non-summarized user messages → inline textarea → Save & Resend deletes forward + re-generates
8. **Delete message**: trash icon on non-summarized messages → confirmation → deletes + adjusts state
9. **Regenerate past turn**: refresh icon on any non-summarized assistant message → rewinds if needed + regenerates
10. **Summarize any message**: "Summarize up to here" works on any non-summarized assistant message from past turns
11. **Unwrap summary**: expand shows original messages inline, collapse hides them
12. **Re-summarize**: regenerate summary button re-runs LLM, updates content
13. **Delete summary**: permanently unwraps messages, summary disappears
14. **Import/export**: thinking_content column handled correctly
15. **All generation modes**: UI works for simple and chain mode, agentic shows appropriate state
