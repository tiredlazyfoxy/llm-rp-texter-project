# Feature 006 — Status

| Step | File                              | Status |
|------|-----------------------------------|--------|
| 001  | `001.summarization_refinement.md` | done |
| 002  | `002.summarization_ui.md`         | done |
| 003  | `003.tool_json_responses.md`      | done |

## Files Changed

### Step 001 + 002 (commits `267fdb3`, `b1ed024`)
- `backend/app/models/schemas/chat.py` — `CompactRequest.variant_index`
- `backend/app/routes/chat.py` — SSE compact route, un-summarize DELETE route
- `backend/app/services/prompts/__init__.py` — export memory extraction prompts
- `backend/app/services/prompts/chat_summarization_prompt.py` — `MEMORY_EXTRACTION_SYSTEM_PROMPT` + `MEMORY_EXTRACTION_USER_PROMPT_TEMPLATE`
- `backend/app/services/summarization_service.py` — `compact_messages_stream()` two-phase async generator, `unsummarize_last()`, variant substitution, clear persisted variants on current-turn compact
- `frontend/src/api/chat.ts` — `compactChatStream()`, `unsummarizeLast()`
- `frontend/src/types/chat.d.ts` — `CompactRequest.variant_index?`
- `frontend/src/user/components/MessageHistory.tsx` — allow compact on last turn, pass variant index, compact progress UI
- `frontend/src/user/components/SummaryBlock.tsx` — `isLast` prop + undo button
- `frontend/src/user/stores/ChatStore.ts` — SSE handlers, compact debug observables, `unsummarizeLast()`

### Step 003 (commit `8fbe5a0`)
- `backend/app/services/chat_tools.py` — JSON responses + ToolSpec description updates for `update_stat` and `move_to_location`
- `frontend/src/user/components/ChatMemoriesModal.tsx` — minor follow-up
