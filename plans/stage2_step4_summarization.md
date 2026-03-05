# Stage 2 Step 4 — Summarization API + UI

## Context

With the chat system running (steps 1–3), this step adds conversation compaction/summarization. As chats grow long, users can compact older messages into LLM-generated summaries, keeping the context window manageable. This affects both the summarization endpoints and the context-building logic in the chat generation service.

---

## 1. Summarization Service

**File**: `backend/app/services/summarization_service.py`

### `compact_messages(session_id, up_to_message_id, db) -> ChatSummary`

Main compaction flow:

1. Load `ChatSession` by ID, verify ownership and `status="active"`.
2. Load target message by `up_to_message_id`, verify it belongs to this session and `role="assistant"`.
3. Determine compaction start point:
   - No previous summaries → start from the first message (after initial system message).
   - Previous summaries exist → start from message after last summary's `end_message_id`.
4. Gather all active messages from start through `up_to_message_id` (inclusive). Filter: `is_active_variant=True`, ordered by `turn_number` ASC, `created_at` ASC.
5. If no messages to summarize (start == end): raise error.
6. Format messages for summarization:
   ```
   Turn 3 - User: I walk into the tavern.
   Turn 3 - Assistant: The tavern is warm and bustling. A barkeep nods at you.
   Turn 4 - User: I approach the barkeep.
   Turn 4 - Assistant: "What'll it be?" the barkeep asks gruffly.
   ```
7. Build LLM request using `SUMMARIZE_SYSTEM_PROMPT` and `SUMMARIZE_USER_PROMPT` from `prompts.py` (defined in step 2).
8. Use session's `llm_model_id` and `llm_server_id` for the call (same model as chat).
9. Call LLM — **non-streaming**, simple completion, **no tools**.
10. Create `ChatSummary` record with response content, message range, turn range.
11. Mark all messages in range as `is_summarized=True`.
12. Return the new `ChatSummary`.

---

## 2. Context Building Update

Modify `build_chat_context()` in `backend/app/services/chat_service.py` (from step 3):

```python
async def build_chat_context(session: ChatSession, db: AsyncSession) -> list[ChatMessageIn]:
    messages = []

    # 1. System prompt (always first)
    system_prompt = build_system_prompt(session, db)
    messages.append(ChatMessageIn(role="system", content=system_prompt))

    # 2. Summaries ordered by start_turn ASC
    summaries = await load_summaries_for_session(session.id, db)
    for summary in summaries:
        messages.append(ChatMessageIn(
            role="system",
            content=f"[Summary of turns {summary.start_turn}–{summary.end_turn}]:\n{summary.content}"
        ))

    # 3. Non-summarized active messages
    raw_messages = await load_active_unsummarized_messages(session.id, db)
    for msg in raw_messages:
        messages.append(ChatMessageIn(role=msg.role, content=msg.content))

    return messages
```

Context = system prompt + [summary blocks] + [raw message tail].

---

## 3. API Endpoints

Extend `backend/app/routes/chat.py` (from step 3).

### Pydantic Schemas

Add to `backend/app/models/schemas/chat.py`:

```python
class CompactRequest(BaseModel):
    up_to_message_id: str  # snowflake as string

class ChatSummaryResponse(BaseModel):
    id: str
    start_message_id: str
    end_message_id: str
    start_turn: int
    end_turn: int
    content: str
    created_at: str

class CompactResponse(BaseModel):
    summary: ChatSummaryResponse
    updated_message_count: int  # how many messages marked as summarized
```

### Endpoints

| Method | Path | Request | Response | Purpose |
|---|---|---|---|---|
| POST | `/api/chats/:id/compact` | `CompactRequest` | `CompactResponse` | Summarize messages up to specified message |
| GET | `/api/chats/:id/summaries` | — | `list[ChatSummaryResponse]` | List all summaries for a chat |
| GET | `/api/chats/:id/messages/original/:summaryId` | — | `list[ChatMessageResponse]` | Get original messages for a summary |

**POST `/api/chats/:id/compact`**:
1. Verify session ownership.
2. Call `compact_messages(session_id, up_to_message_id, db)`.
3. Return summary and count of affected messages.

**GET `/api/chats/:id/summaries`**:
- Returns all summaries ordered by `start_turn` ASC.

**GET `/api/chats/:id/messages/original/:summaryId`**:
- Load all messages between `summary.start_message_id` and `summary.end_message_id` (inclusive).
- Used by frontend to show original messages when expanding a summary.

---

## 4. ChatDetailResponse Update

Extend the response from step 3 to include summaries:

```python
class ChatDetailResponse(BaseModel):
    session: ChatSessionResponse
    messages: list[ChatMessageResponse]       # non-summarized active messages
    snapshots: list[ChatStateSnapshotResponse]
    variants: list[ChatMessageResponse]       # variants for latest turn
    summaries: list[ChatSummaryResponse]      # all summaries for this session
```

---

## 5. Frontend — TypeScript Types

Add to `frontend/src/types/chat.d.ts`:

```typescript
interface ChatSummary {
  id: string;
  start_message_id: string;
  end_message_id: string;
  start_turn: number;
  end_turn: number;
  content: string;
  created_at: string;
}

interface CompactRequest {
  up_to_message_id: string;
}

interface CompactResponse {
  summary: ChatSummary;
  updated_message_count: number;
}
```

Update `ChatDetail` to include `summaries: ChatSummary[]`.

---

## 6. Frontend — API Client Extensions

Add to `frontend/src/api/chat.ts`:

```typescript
async function compactChat(chatId: string, req: CompactRequest): Promise<CompactResponse>;
async function listSummaries(chatId: string): Promise<ChatSummary[]>;
async function getOriginalMessages(chatId: string, summaryId: string): Promise<ChatMessage[]>;
```

---

## 7. Frontend — MobX Store Extensions

Add to `ChatStore` in `frontend/src/user/stores/ChatStore.ts`:

```typescript
// Additional observable state
summaries: ChatSummary[] = [];
expandedSummaryMessages: Map<string, ChatMessage[]> = new Map();  // summaryId -> original messages
isCompacting: boolean = false;

// Additional actions
async compactUpTo(messageId: string): Promise<void>;
async loadSummaries(): Promise<void>;
async expandSummary(summaryId: string): Promise<void>;
collapseSummary(summaryId: string): void;

// Updated computed
get displayItems(): Array<ChatMessage | ChatSummary>;
// Interleaved list of summaries and non-summarized messages in chronological order.
// ChatViewPage renders this: SummaryBlock for summaries, MessageBubble for messages.
```

---

## 8. Frontend — Components

### SummaryBlock — `frontend/src/user/components/SummaryBlock.tsx`

- Displayed inline in message history where summarized messages would have been
- Distinct styling: muted background color, border, "Summary" label
- Shows summary content as text
- Turn range: "Turns N–M summarized"
- **Expand button**: loads original messages via `getOriginalMessages()`, shows in a sub-list with dimmed/indented styling
- **Collapse button**: hides expanded original messages

### MessageHistory Update — `frontend/src/user/components/MessageHistory.tsx`

Modify from step 3:
- Render from `displayItems` computed (interleaved summaries + messages)
- For each item:
  - `ChatSummary` → render `<SummaryBlock>`
  - `ChatMessage` → render `<MessageBubble>` as before
- **Compact button**: shown on each assistant message that is:
  - NOT already summarized
  - NOT the latest turn (need messages after summary for chat to continue)
- Click → confirm dialog ("Summarize all messages up to this point?") → `compactUpTo(messageId)`
- While compacting: spinner/loading overlay

### Button Layout on Assistant Messages

```
+--------------------------------------+
|  [Assistant message content...]      |
|                                      |
|  [Compact] [Rewind]     Turn 5      |
+--------------------------------------+
```

---

## 9. Rewind + Summary Interaction

Already handled by `rewind_to_turn()` in step 3:
- Deletes summaries whose `end_turn > target_turn`
- For summaries where `start_turn <= target_turn < end_turn`: deletes entire summary
- Restores `is_summarized=False` on messages covered by deleted summaries
- Frontend reloads full chat detail after rewind

---

## New Files

| File | Purpose |
|---|---|
| `backend/app/services/summarization_service.py` | Compaction logic, LLM summarization call |
| `frontend/src/user/components/SummaryBlock.tsx` | Summary display component |

## Modified Files

| File | Change |
|---|---|
| `backend/app/routes/chat.py` | Add compact, summaries, original-messages endpoints |
| `backend/app/models/schemas/chat.py` | Add CompactRequest, ChatSummaryResponse, CompactResponse; update ChatDetailResponse |
| `backend/app/services/chat_service.py` | Update `build_chat_context()` to incorporate summaries |
| `frontend/src/types/chat.d.ts` | Add ChatSummary, CompactRequest, CompactResponse; update ChatDetail |
| `frontend/src/api/chat.ts` | Add compactChat, listSummaries, getOriginalMessages |
| `frontend/src/user/stores/ChatStore.ts` | Add summary state, compaction actions, displayItems computed |
| `frontend/src/user/components/MessageHistory.tsx` | Render summaries inline, add compact button |
| `frontend/src/user/pages/ChatViewPage.tsx` | Wire up summary display |

---

## Role Permissions

| Action | Required Role |
|---|---|
| Compact own chat | player |
| View summaries of own chat | player |
| Expand summary to see originals | player |

---

## Dependencies

- Stage 2 Step 1 (ChatSummary model)
- Stage 2 Step 2 (prompts: SUMMARIZE_SYSTEM_PROMPT, SUMMARIZE_USER_PROMPT)
- Stage 2 Step 3 (chat API, context building, chat UI)

---

## Verification

1. Create a chat and generate 5–6 turns of conversation
2. **Compact**: POST `/api/chats/:id/compact` with mid-conversation assistant message ID → verify summary created, messages marked as summarized
3. **Context building**: Send new message after compaction → verify LLM receives summary block + raw tail (check DEBUG logs)
4. **Multiple compactions**: Compact again at a later message → verify second summary starts after first ends
5. **Expand**: GET original messages for a summary → verify all messages in range returned
6. **Rewind through summary**: Rewind to a turn within a summarized range → verify summary deleted, messages restored
7. **Frontend**: Summary blocks appear inline with distinct styling
8. **Frontend**: Click "Compact" on assistant message → loading → summary block replaces messages
9. **Frontend**: Click "Expand" on summary → original messages shown below
10. **Frontend**: Compact button NOT shown on latest turn's assistant message
11. **Export**: DB export includes `chat_summaries.jsonl.gz`; import restores correctly
