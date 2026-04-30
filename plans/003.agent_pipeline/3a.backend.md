# Stage 3 Step 3a — Backend: thinking_content, Message Edit/Delete, Response Schema Updates

## Context

Step 2 implemented generation backends (simple + chain modes) with SSE streaming. The backend already emits `phase` and `status` SSE events, stores `generation_plan` on messages, and filters events by caller role. This sub-step adds: storing thinking content on messages, message edit/delete endpoints, and response schema additions needed by the frontend.

### Dependencies

- Stage 3 Step 2a (simple mode, SSE events, chat tools)
- Stage 3 Step 2b (chain mode, generation_plan, phase/status events)

---

## 1. ChatMessage Model — Add `thinking_content`

### 1a. Model — `backend/app/models/chat_message.py`

Add column:

```python
thinking_content: str | None = Field(default=None)
```

Currently, thinking content is streamed via SSE but discarded after generation. This column persists it so debug mode can show thinking on already-loaded messages.

### 1b. Import/Export — `backend/app/services/db_import_export.py`

Add `thinking_content` to both serialization functions:

```python
# _chat_message_to_dict()
"thinking_content": m.thinking_content,

# _dict_to_chat_message()
thinking_content=d.get("thinking_content"),
```

Backward-compatible: missing key defaults to None.

---

## 2. Save thinking_content in Generation Services

### 2a. Simple Mode — `backend/app/services/simple_generation_service.py`

The `create_thinking_callback()` in `chat_agent_service.py` already collects thinking parts for SSE streaming. Need to:

1. Collect all thinking content during generation (it's already in callback but not accumulated for saving)
2. After generation completes, join thinking parts into a single string
3. Pass `thinking_content` when creating the assistant `ChatMessage`

Look at how `content_parts` are accumulated — do the same for thinking. The callback in `chat_agent_service.py` (lines 116-162) handles `on_delta` events, distinguishing `thinking` vs `content` delta types.

### 2b. Chain Mode — `backend/app/services/chain_generation_service.py`

Planning stage thinking content: `_create_filtered_thinking_callback()` already streams thinking SSE events. Need to:

1. Accumulate planning-stage thinking parts
2. Optionally also accumulate writing-stage thinking (if the writing LLM produces thinking)
3. Save combined thinking content on the assistant message

The assistant message is created at the end of the chain (after writing stage). Add `thinking_content=combined_thinking` to the ChatMessage constructor.

---

## 3. Response Schema Updates

### 3a. ChatMessageResponse — `backend/app/models/schemas/chat.py`

Add fields:

```python
thinking_content: str | None = None
```

The `generation_plan` field already exists on `ChatMessageResponse`.

### 3b. WorldInfoResponse — `backend/app/models/schemas/chat.py`

Add field:

```python
generation_mode: str  # "simple" | "chain" | "agentic"
```

Frontend needs this to know which generation mode a world uses. `generation_mode` is on the `World` model, not on `ChatSession`.

### 3c. StatDefinition in WorldInfoResponse

Verify that `hidden: bool` is already included in the stat definition response. If not, add it. The `WorldStatDefinition` model has `hidden` — make sure it's exposed in the API response.

---

## 4. Message Edit Endpoint

### 4a. Request Schema — `backend/app/models/schemas/chat.py`

```python
class EditMessageRequest(BaseModel):
    content: str
```

### 4b. Route — `backend/app/routes/chat.py`

```python
@router.put("/{chat_id}/messages/{message_id}")
async def edit_message(chat_id: str, message_id: str, req: EditMessageRequest, caller=Depends(_require_player)):
    detail = await chat_service.edit_message(int(chat_id), int(message_id), req.content, caller.id)
    return detail
```

### 4c. Service — `backend/app/services/chat_service.py`

```python
async def edit_message(session_id: int, message_id: int, new_content: str, user_id: int) -> ChatDetailResponse:
```

Flow:
1. Load message, validate: belongs to session, is user role, is non-summarized (`summary_id is None`)
2. Update message content in DB
3. Delete all messages AFTER this message's turn_number (assistant at same turn + all future turns)
4. Delete snapshots after this turn (keep snapshot at `turn_number - 1`)
5. Delete summaries that overlap with deleted range
6. Restore session state from snapshot at `turn_number - 1`
7. Set session `current_turn = turn_number - 1` (next send will increment to correct turn)
8. Return updated `ChatDetailResponse`

Reuse existing functions:
- `chats_db.delete_messages_after_turn()` — but need to also delete assistant messages AT the same turn (this deletes only AFTER)
- `chats_db.delete_snapshots_after_turn()`
- `chats_db.delete_summaries_after_turn()`
- Rewind state restoration pattern from `rewind_chat()`

### 4d. DB Layer — `backend/app/db/chats.py`

```python
async def update_message_content(message_id: int, content: str) -> None:
    """Update only the content field of a message."""

async def delete_messages_at_and_after_turn(session_id: int, turn_number: int, exclude_role: str | None = None) -> None:
    """Delete messages at turn_number (optionally excluding a role) and all messages after turn_number."""
```

The second function is needed because `edit_message` must keep the edited user message but delete assistant messages at the same turn + everything after.

---

## 5. Message Delete Endpoint

### 5a. Route — `backend/app/routes/chat.py`

```python
@router.delete("/{chat_id}/messages/{message_id}")
async def delete_message(chat_id: str, message_id: str, caller=Depends(_require_player)):
    detail = await chat_service.delete_message(int(chat_id), int(message_id), caller.id)
    return detail
```

### 5b. Service — `backend/app/services/chat_service.py`

```python
async def delete_message(session_id: int, message_id: int, user_id: int) -> ChatDetailResponse:
```

Flow (updated — delete this specific message + everything after):
1. Load message, validate: belongs to session, is non-summarized, is not system role
2. **If user message**: delete this specific message by ID, delete assistant messages at this turn, delete all messages at `turn + 1` onward. Other user messages at the same turn (duplicates from stop+resend) are preserved. Rewind to `turn - 1`.
3. **If assistant message**: mark all assistant variants at this turn inactive. Delete all messages at `turn + 1` onward (keep user messages at this turn). Rewind to `turn - 1`.
4. Clean up snapshots/summaries after rewind point. Restore state from snapshot.
5. Return updated `ChatDetailResponse`

---

## 6. Regenerate with Optional turn_number

### 6a. Request Schema — `backend/app/models/schemas/chat.py`

```python
class RegenerateRequest(BaseModel):
    turn_number: int | None = None
```

### 6b. Route — `backend/app/routes/chat.py`

Update existing regenerate endpoint to accept optional body:

```python
@router.post("/{chat_id}/regenerate")
async def regenerate(chat_id: str, req: RegenerateRequest | None = None, caller=Depends(_require_player)):
    turn = req.turn_number if req else None
    # If turn specified and < current_turn: rewind first, then regenerate
```

### 6c. Service — `backend/app/services/chat_agent_service.py`

Update `regenerate_response()` to accept optional `turn_number`:
- If `turn_number` is None or equals `current_turn`: existing behavior
- If `turn_number < current_turn`: call rewind to that turn first, then regenerate

---

## 7. Files Summary

| File | Change |
| ---- | ---- |
| `backend/app/models/chat_message.py` | Add `thinking_content` column |
| `backend/app/models/schemas/chat.py` | `EditMessageRequest`, `RegenerateRequest`, `thinking_content` on message response, `generation_mode` on world info, verify `hidden` on stat def |
| `backend/app/db/chats.py` | `update_message_content()`, `delete_messages_at_and_after_turn()` |
| `backend/app/services/chat_service.py` | `edit_message()`, `delete_message()` |
| `backend/app/services/chat_agent_service.py` | `regenerate_response()` accepts optional `turn_number` |
| `backend/app/services/simple_generation_service.py` | Accumulate + save `thinking_content` |
| `backend/app/services/chain_generation_service.py` | Accumulate + save `thinking_content` |
| `backend/app/services/db_import_export.py` | Add `thinking_content` to ChatMessage serialization |
| `backend/app/routes/chat.py` | New PUT/DELETE message endpoints, update regenerate to accept `turn_number` |

---

## 8. Verification

1. **thinking_content saved**: after simple/chain generation, check DB — `thinking_content` column populated on assistant message
2. **Edit message**: PUT endpoint updates content, deletes forward messages/snapshots, rewinds state correctly
3. **Delete message (latest turn)**: DELETE endpoint removes message, adjusts turn counter, restores state
4. **Delete message (past turn)**: DELETE endpoint rewinds to before that turn
5. **Regenerate past turn**: POST regenerate with `turn_number` rewinds + regenerates
6. **Import/export**: thinking_content round-trips correctly through JSONL export/import
7. **WorldInfo response**: includes `generation_mode`
8. **StatDefinition response**: includes `hidden` field
