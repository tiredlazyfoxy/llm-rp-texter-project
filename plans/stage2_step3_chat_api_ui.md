# Stage 2 Step 3 — Chat API + UI

## Context

With chat database models (step 1) and tools/prompts (step 2) in place, this step builds the full chat system: the generation service, API routes with SSE streaming, and the user-facing frontend. This is the core gameplay loop — users select a world, create a character, and engage in LLM-driven RP conversation.

---

## 1. Chat Generation Service

**File**: `backend/app/services/chat_service.py`

### `build_chat_context(session, db) -> list[ChatMessageIn]`

Builds the message list for the LLM call:

1. System message from `CHAT_SYSTEM_PROMPT` (from `prompts.py`) with all variables interpolated using helpers from `chat_tools.py`.
2. For summarized sections: inject summary content as system message: `"[Summary of turns {start}–{end}]:\n{summary.content}"`.
3. For non-summarized active messages: include as-is with their role.
4. Returns the full message list ready for LLM.

### `generate_response(session_id, user_message, db) -> AsyncGenerator[SSEEvent]`

Main generation flow, yields SSE events:

1. Load `ChatSession` by ID, verify status is `"active"`, verify ownership.
2. Save user message as `ChatMessage(role="user", turn_number=session.current_turn + 1, is_active_variant=True)`.
3. Build context via `build_chat_context()`.
4. Get LLM client via `get_llm_client_for_model(session.llm_model_id, db)` (from stage 1 step 5).
5. Get tools via `get_chat_tools(db, session.world_id)` (from step 2).
6. Call LLM with tools — **single step** (`max_loops=1`), **streaming**, using `session.temperature`.
7. Yield SSE events as they arrive:
   - `thinking` events for reasoning tokens (collapsed in UI)
   - `thinking_done` when reasoning ends
   - `tool_call_start` when tool invocation begins
   - `tool_call_result` when tool returns
   - `token` events for content deltas
8. After stream completes: parse `[STAT_UPDATE]` block from full response using `parse_stat_updates()`.
9. Validate and apply stat updates via `validate_and_apply_stat_updates()`.
10. Save assistant message as `ChatMessage(role="assistant", turn_number=session.current_turn + 1, tool_calls=<json>, is_active_variant=True)`.
11. Increment `session.current_turn`.
12. Save `ChatStateSnapshot` for the new turn.
13. Yield `stat_update` event with changed stats.
14. Yield `done` event with final `ChatMessageResponse`.

**Logging**: All tool calls and results logged at DEBUG level on the server side.

### `regenerate_response(session_id, db) -> AsyncGenerator[SSEEvent]`

1. Load session, find latest turn's active assistant message.
2. Set `is_active_variant=False` on current active assistant message.
3. Revert session stats to snapshot for `current_turn - 1` (state before this turn).
4. Re-run generation with the same user message (reload from `ChatMessage` where `turn_number=current_turn`, `role="user"`).
5. New assistant message gets `is_active_variant=True`.
6. Update snapshot for current turn with new stats.
7. Yields same SSE events as `generate_response`.

### `continue_chat(session_id, selected_variant_id, db)`

1. Verify selected variant exists and belongs to latest turn.
2. Delete all assistant messages for this turn where `id != selected_variant_id`.
3. Ensure `is_active_variant=True` on selected message.

### `rewind_to_turn(session_id, target_turn, db)`

1. Delete all `ChatMessage` rows where `turn_number > target_turn`.
2. Delete all `ChatStateSnapshot` rows where `turn_number > target_turn`.
3. Delete any `ChatSummary` rows whose `end_turn > target_turn`. If a summary's `start_turn <= target_turn < end_turn`, delete the entire summary and restore `is_summarized=False` on affected messages.
4. Restore session stats from snapshot at `target_turn`.
5. Set `session.current_turn = target_turn`.

---

## 2. SSE Streaming Protocol

Chat responses stream via SSE, extending the pattern from stage 1 step 5 (document editor) with additional events for tool tracing and thinking.

### SSE Events

| Event | Data | When |
|---|---|---|
| `thinking` | `{"content": "...delta..."}` | Reasoning/thinking token delta |
| `thinking_done` | `{}` | End of thinking block |
| `tool_call_start` | `{"tool_name": "...", "arguments": {...}}` | Tool invocation begins |
| `tool_call_result` | `{"tool_name": "...", "result": "..."}` | Tool returned result |
| `token` | `{"content": "...delta..."}` | Content token delta |
| `stat_update` | `{"stats": {"name": value, ...}}` | Stats changed after generation |
| `done` | `{"message": ChatMessageResponse}` | Final complete message object |
| `error` | `{"detail": "..."}` | Error during generation |

### Event Ordering

Typical sequence: `thinking*` → `thinking_done` → `tool_call_start` → `tool_call_result` → `token*` → `stat_update?` → `done`

---

## 3. API Endpoints

**File**: `backend/app/routes/chat.py`

All endpoints require **player** role (any authenticated user). Mounted at `/api/chats`.

### Pydantic Schemas

**File**: `backend/app/models/schemas/chat.py`

#### Request Schemas

```python
class CreateChatRequest(BaseModel):
    world_id: str                         # snowflake as string
    character_name: str
    template_variables: dict[str, str]    # placeholder name -> value
    starting_location_id: str             # snowflake as string
    llm_model_id: str                     # which model to use

class SendMessageRequest(BaseModel):
    content: str

class ContinueRequest(BaseModel):
    selected_variant_id: str              # snowflake as string

class RewindRequest(BaseModel):
    target_turn: int

class UpdateChatSettingsRequest(BaseModel):
    temperature: float | None = None      # 0.0–2.0, None = keep current
    user_instructions: str | None = None  # None = keep current
```

#### Response Schemas

```python
class ChatSessionResponse(BaseModel):
    id: str
    world_id: str
    world_name: str                       # denormalized for display
    character_name: str
    character_description: str
    character_stats: dict[str, int | str | list[str]]
    world_stats: dict[str, int | str | list[str]]
    current_location_id: str | None
    current_location_name: str | None     # denormalized for display
    current_turn: int
    status: str
    llm_model_id: str | None
    temperature: float
    user_instructions: str
    created_at: str
    modified_at: str

class ChatSessionListItem(BaseModel):
    id: str
    world_name: str
    character_name: str
    current_turn: int
    status: str
    modified_at: str

class ChatSessionListResponse(BaseModel):
    items: list[ChatSessionListItem]

class ToolCallInfo(BaseModel):
    tool_name: str
    arguments: dict[str, str]
    result: str

class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    turn_number: int
    tool_calls: list[ToolCallInfo] | None
    is_active_variant: bool
    created_at: str

class ChatStateSnapshotResponse(BaseModel):
    turn_number: int
    location_id: str | None
    location_name: str | None
    character_stats: dict[str, int | str | list[str]]
    world_stats: dict[str, int | str | list[str]]

class ChatDetailResponse(BaseModel):
    session: ChatSessionResponse
    messages: list[ChatMessageResponse]
    snapshots: list[ChatStateSnapshotResponse]
    variants: list[ChatMessageResponse]   # all variants for latest turn

class LocationBrief(BaseModel):
    id: str
    name: str

class StatDefinitionResponse(BaseModel):
    name: str
    description: str
    scope: str
    stat_type: str
    default_value: str
    min_value: int | None
    max_value: int | None
    enum_values: list[str] | None

class WorldInfoResponse(BaseModel):
    id: str
    name: str
    description: str
    lore: str
    character_template: str
    locations: list[LocationBrief]
    stat_definitions: list[StatDefinitionResponse]
```

### Endpoints

| Method | Path | Request | Response | Purpose |
|---|---|---|---|---|
| GET | `/api/chats/worlds` | — | `list[WorldInfoResponse]` | List public worlds for selection |
| POST | `/api/chats` | `CreateChatRequest` | `ChatSessionResponse` | Create new chat session |
| GET | `/api/chats` | — | `ChatSessionListResponse` | List user's chat sessions |
| GET | `/api/chats/:id` | — | `ChatDetailResponse` | Get chat with messages and state |
| POST | `/api/chats/:id/message` | `SendMessageRequest` | SSE stream | Send message, stream LLM response |
| POST | `/api/chats/:id/regenerate` | — | SSE stream | Regenerate last assistant message |
| POST | `/api/chats/:id/continue` | `ContinueRequest` | `{"ok": true}` | Pick variant, delete others |
| POST | `/api/chats/:id/rewind` | `RewindRequest` | `ChatDetailResponse` | Rewind to target turn |
| PUT | `/api/chats/:id/model` | `{"llm_model_id": str}` | `{"ok": true}` | Change LLM model for chat |
| PUT | `/api/chats/:id/settings` | `UpdateChatSettingsRequest` | `{"ok": true}` | Update chat settings (temperature, instructions) |
| PUT | `/api/chats/:id/archive` | — | `{"ok": true}` | Archive chat (make read-only) |
| DELETE | `/api/chats/:id` | — | `{"ok": true}` | Delete chat and all related data |

### Endpoint Details

**GET `/api/chats/worlds`**:
- Filter worlds where `status = "public"`
- Include locations (id + name) and stat definitions
- Include `character_template` so UI can extract `{PLACEHOLDER}` tokens

**POST `/api/chats`**:
1. Load world, verify `status = "public"`
2. Verify model is available (exists in an active server's enabled list)
3. Parse `character_template` — extract `{PLACEHOLDER}` tokens, verify `template_variables` provides all values
4. Build `character_description` by replacing placeholders
5. Initialize stats from `WorldStatDefinition` defaults
6. Create `ChatSession`, `ChatStateSnapshot` (turn 0), initial system `ChatMessage` using `CHAT_INITIAL_MESSAGE`
7. Return new session

**POST `/api/chats/:id/message`** and **POST `/api/chats/:id/regenerate`**:
- Return SSE `StreamingResponse` from FastAPI
- Content-Type: `text/event-stream`

**DELETE `/api/chats/:id`**:
1. Verify session ownership.
2. Delete all related data in order (FK deps): `chat_summaries` → `chat_state_snapshots` → `chat_messages` → `chat_sessions`.
3. Return `{"ok": true}`.

**Authorization**: Every endpoint verifies `session.user_id == current_user.id`.

---

## 4. Frontend — TypeScript Types

**File**: `frontend/src/types/chat.d.ts`

```typescript
interface ChatSessionItem {
  id: string;
  world_name: string;
  character_name: string;
  current_turn: number;
  status: "active" | "archived";
  modified_at: string;
}

interface ChatSession {
  id: string;
  world_id: string;
  world_name: string;
  character_name: string;
  character_description: string;
  character_stats: Record<string, number | string | string[]>;
  world_stats: Record<string, number | string | string[]>;
  current_location_id: string | null;
  current_location_name: string | null;
  current_turn: number;
  status: "active" | "archived";
  llm_model_id: string | null;
  temperature: number;
  user_instructions: string;
  created_at: string;
  modified_at: string;
}

interface UpdateChatSettingsRequest {
  temperature?: number;
  user_instructions?: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  turn_number: number;
  tool_calls: ToolCallInfo[] | null;
  is_active_variant: boolean;
  created_at: string;
}

interface ToolCallInfo {
  tool_name: string;
  arguments: Record<string, string>;
  result: string;
}

interface ChatStateSnapshot {
  turn_number: number;
  location_id: string | null;
  location_name: string | null;
  character_stats: Record<string, number | string | string[]>;
  world_stats: Record<string, number | string | string[]>;
}

interface ChatDetail {
  session: ChatSession;
  messages: ChatMessage[];
  snapshots: ChatStateSnapshot[];
  variants: ChatMessage[];
}

interface WorldInfo {
  id: string;
  name: string;
  description: string;
  lore: string;
  character_template: string;
  locations: LocationBrief[];
  stat_definitions: StatDefinition[];
}

interface LocationBrief {
  id: string;
  name: string;
}

interface StatDefinition {
  name: string;
  description: string;
  scope: "character" | "world";
  stat_type: "int" | "enum" | "set";
  default_value: string;
  min_value: number | null;
  max_value: number | null;
  enum_values: string[] | null;
}

interface CreateChatRequest {
  world_id: string;
  character_name: string;
  template_variables: Record<string, string>;
  starting_location_id: string;
  llm_model_id: string;
}

interface SendMessageRequest {
  content: string;
}

interface ContinueRequest {
  selected_variant_id: string;
}

interface RewindRequest {
  target_turn: number;
}

// SSE event types
interface SSETokenEvent {
  content: string;
}

interface SSEThinkingEvent {
  content: string;
}

interface SSEToolCallStartEvent {
  tool_name: string;
  arguments: Record<string, string>;
}

interface SSEToolCallResultEvent {
  tool_name: string;
  result: string;
}

interface SSEStatUpdateEvent {
  stats: Record<string, number | string | string[]>;
}

interface SSEDoneEvent {
  message: ChatMessage;
}

interface SSEErrorEvent {
  detail: string;
}
```

---

## 5. Frontend — API Client

**File**: `frontend/src/api/chat.ts`

```typescript
// Standard REST endpoints (use JWT from localStorage)
async function listPublicWorlds(): Promise<WorldInfo[]>;
async function createChat(req: CreateChatRequest): Promise<ChatSession>;
async function listMyChats(): Promise<ChatSessionItem[]>;
async function getChatDetail(chatId: string): Promise<ChatDetail>;
async function continueChat(chatId: string, req: ContinueRequest): Promise<void>;
async function rewindChat(chatId: string, req: RewindRequest): Promise<ChatDetail>;
async function changeChatModel(chatId: string, modelId: string): Promise<void>;
async function updateChatSettings(chatId: string, req: UpdateChatSettingsRequest): Promise<void>;
async function archiveChat(chatId: string): Promise<void>;
async function deleteChat(chatId: string): Promise<void>;

// SSE streaming endpoints (fetch + ReadableStream)
function sendMessage(chatId: string, req: SendMessageRequest, handlers: SSEHandlers): AbortController;
function regenerateMessage(chatId: string, handlers: SSEHandlers): AbortController;

interface SSEHandlers {
  onToken: (event: SSETokenEvent) => void;
  onThinking: (event: SSEThinkingEvent) => void;
  onThinkingDone: () => void;
  onToolCallStart: (event: SSEToolCallStartEvent) => void;
  onToolCallResult: (event: SSEToolCallResultEvent) => void;
  onStatUpdate: (event: SSEStatUpdateEvent) => void;
  onDone: (event: SSEDoneEvent) => void;
  onError: (event: SSEErrorEvent) => void;
}
```

SSE streaming uses `fetch` with `ReadableStream` (not `EventSource`, since we need POST with body and auth headers).

---

## 6. Frontend — MobX Store

**File**: `frontend/src/user/stores/ChatStore.ts`

```typescript
class ChatStore {
  // Observable state
  publicWorlds: WorldInfo[] = [];
  myChatList: ChatSessionItem[] = [];
  currentChat: ChatDetail | null = null;
  isLoading: boolean = false;
  isSending: boolean = false;
  error: string | null = null;

  // Streaming state
  streamingContent: string = "";
  streamingThinking: string = "";
  streamingToolCalls: Array<{tool_name: string; arguments: Record<string,string>; result?: string}> = [];
  isThinking: boolean = false;

  // Actions
  async loadPublicWorlds(): Promise<void>;
  async loadMyChatList(): Promise<void>;
  async loadChatDetail(chatId: string): Promise<void>;
  async createNewChat(req: CreateChatRequest): Promise<string>;  // returns chat ID
  async sendMessage(content: string): Promise<void>;  // manages SSE streaming
  async regenerate(): Promise<void>;  // manages SSE streaming
  async continueWithVariant(variantId: string): Promise<void>;
  async rewindToTurn(turn: number): Promise<void>;
  async changeModel(modelId: string): Promise<void>;
  async updateSettings(req: UpdateChatSettingsRequest): Promise<void>;
  async archiveChat(): Promise<void>;
  async deleteChat(): Promise<void>;  // delete current chat, navigate to list
  stopGeneration(): void;  // abort current SSE stream

  // Computed
  get activeMessages(): ChatMessage[];       // is_active_variant=true
  get latestTurnVariants(): ChatMessage[];   // all variants for last turn
  get hasMultipleVariants(): boolean;
  get currentSnapshot(): ChatStateSnapshot | null;
}
```

---

## 7. Frontend — Pages

### Router Setup

**File**: `frontend/src/user/App.tsx`

Routes:
- `/` → `ChatListPage`
- `/worlds` → `WorldSelectPage`
- `/worlds/:worldId/new` → `CharacterSetupPage`
- `/chat/:chatId` → `ChatViewPage`

### ChatListPage — `frontend/src/user/pages/ChatListPage.tsx`

- Lists user's existing chats (table/card list)
- Columns: World name, Character name, Turn count, Status, Last modified, Actions
- Click → navigate to `/chat/:chatId`
- Delete button per chat → confirm dialog → `deleteChat(chatId)` → remove from list
- "New Chat" button → navigate to `/worlds`

### WorldSelectPage — `frontend/src/user/pages/WorldSelectPage.tsx`

- Lists all public worlds as Mantine Cards
- Each card: name, description excerpt, lore excerpt
- Click → navigate to `/worlds/:worldId/new`

### CharacterSetupPage — `frontend/src/user/pages/CharacterSetupPage.tsx`

- Loads `WorldInfo` for selected world
- Parses `character_template` to extract `{PLACEHOLDER}` tokens
- Displays:
  - World name and description (read-only preview)
  - Input field for each placeholder (`{NAME}` always first)
  - Location picker: dropdown of world locations
  - Model picker: dropdown of enabled models (reuses `GET /api/llm/models` from stage 1 step 3)
  - "Start Adventure" button
- On submit: `createChat()` → navigate to `/chat/:chatId`

### ChatViewPage — `frontend/src/user/pages/ChatViewPage.tsx`

Main chat interface layout:

```
+-----------------------------------------------+
|  Header: World name — Character name    [Menu] |
+--------------------+--------------------------+
|                    |  Stats Panel (collapsible)|
|  Message History   |  - Character stats       |
|  (scrollable)      |  - World stats           |
|                    |  - Current location      |
|                    +--------------------------+
|                    |
+--------------------+
|  Input Area                                    |
+-----------------------------------------------+
```

---

## 8. Frontend — Components

### MessageHistory — `frontend/src/user/components/MessageHistory.tsx`

- Renders messages ordered by turn_number (filtered to `is_active_variant=true` except latest turn variants)
- System messages: italic/dimmed narrative style
- Per-turn divider with turn number and location indicator (if changed)
- Auto-scroll to bottom on new messages
- Summary blocks rendered inline (prepared for step 4)

### MessageBubble — `frontend/src/user/components/MessageBubble.tsx`

- User messages: right-aligned bubble
- Assistant messages: left-aligned bubble, markdown rendered
- **Tool call trace**: collapsible section showing each tool call (name, arguments, result) — collapsed by default
- **Thinking trace**: collapsible section showing reasoning — collapsed by default
- **Rewind button**: small icon on each assistant message, click → confirm → `rewindToTurn(turn_number - 1)`

### VariantSelector — `frontend/src/user/components/VariantSelector.tsx`

- Shown only when `hasMultipleVariants` is true
- "Variant 1/3" with prev/next arrows
- Shows selected variant's content
- "Continue with this" button → `continueWithVariant(selectedId)`

### StatsPanel — `frontend/src/user/components/StatsPanel.tsx`

- Collapsible sidebar/drawer
- Character stats and world stats sections
- Per stat: name + value display
  - int: progress bar (with min/max from definition)
  - enum: badge
  - set: tag list
- Updates on each turn from latest snapshot or session stats

### ChatInput — `frontend/src/user/components/ChatInput.tsx`

- Textarea: Enter to send, Shift+Enter for newline
- Send button (disabled while `isSending`)
- Stop button (visible during generation, calls `stopGeneration()`)
- Loading/streaming indicator
- **Regenerate button**: visible after last assistant message, calls `regenerate()`

### ToolCallTrace — `frontend/src/user/components/ToolCallTrace.tsx`

- Collapsible panel embedded in MessageBubble
- For each tool call: tool name, arguments (formatted JSON), result (formatted/truncated)
- Shows during streaming via `streamingToolCalls` observable
- Persisted in final message via `tool_calls` field

### ChatSettingsPanel — `frontend/src/user/components/ChatSettingsPanel.tsx`

- Hidden/collapsible drawer or panel, toggled from the header [Menu] or a gear icon
- **Temperature**: slider (0.0–2.0, step 0.1), shows current value
- **User Instructions**: multi-line textarea for additional instructions appended to the system prompt
- **Model picker**: dropdown to change LLM model (reuses enabled models list)
- "Save" button → calls `updateSettings()` and/or `changeModel()`
- Changes take effect on the next LLM call (no retroactive effect)

---

## New Files

| File | Purpose |
|---|---|
| `backend/app/services/chat_service.py` | Chat generation, regeneration, rewind, context building |
| `backend/app/routes/chat.py` | Chat API endpoints |
| `backend/app/models/schemas/chat.py` | Pydantic request/response schemas |
| `frontend/src/types/chat.d.ts` | TypeScript interfaces |
| `frontend/src/api/chat.ts` | API client functions |
| `frontend/src/user/stores/ChatStore.ts` | MobX store |
| `frontend/src/user/pages/ChatListPage.tsx` | Chat sessions list |
| `frontend/src/user/pages/WorldSelectPage.tsx` | World selection |
| `frontend/src/user/pages/CharacterSetupPage.tsx` | Character creation |
| `frontend/src/user/pages/ChatViewPage.tsx` | Main chat view |
| `frontend/src/user/components/MessageHistory.tsx` | Message list |
| `frontend/src/user/components/MessageBubble.tsx` | Individual message display |
| `frontend/src/user/components/VariantSelector.tsx` | Regeneration variant picker |
| `frontend/src/user/components/StatsPanel.tsx` | Stats display |
| `frontend/src/user/components/ChatInput.tsx` | Message input |
| `frontend/src/user/components/ToolCallTrace.tsx` | Tool call display |
| `frontend/src/user/components/ChatSettingsPanel.tsx` | Hidden settings panel (temperature, instructions, model) |

## Modified Files

| File | Change |
|---|---|
| `backend/app/main.py` | Mount chat router at `/api/chats` |
| `frontend/src/user/App.tsx` | Add routes, ChatStore provider |

---

## Role Permissions

| Action | Required Role |
|---|---|
| List public worlds | player |
| Create/manage/delete own chats | player |
| Send messages, regenerate, rewind | player |
| Access other users' chats | **never** |

---

## Dependencies

- Stage 2 Step 1 (chat DB models)
- Stage 2 Step 2 (prompts, tools, NPC logic, stat parsing)
- Stage 1 Step 2 (world models, vector storage)
- Stage 1 Step 3 (LLM server management, model list endpoint)
- Stage 1 Step 5 (`get_llm_client_for_model`, SSE streaming pattern)

---

## Verification

1. **Create chat**: POST `/api/chats` with valid world, character variables, location → verify session created with initialized stats, turn 0 snapshot, initial system message
2. **Send message**: POST `/api/chats/:id/message` → verify SSE stream: thinking events, tool call events, token events, stat_update, done
3. **Tool tracing**: Verify tool_call_start and tool_call_result events contain correct data, logged server-side at DEBUG
4. **Thinking**: Verify thinking events stream collapsed reasoning, thinking_done fires
5. **Regenerate**: POST `/api/chats/:id/regenerate` → verify new variant created, old marked inactive, SSE stream works
6. **Continue**: POST `/api/chats/:id/continue` → verify non-selected variants deleted
7. **Rewind**: POST `/api/chats/:id/rewind` → verify messages/snapshots deleted, stats restored
8. **Authorization**: User A cannot access user B's chats
9. **Frontend**: Navigate world selection → character setup → chat view, send messages
10. **Frontend**: Test SSE streaming display: content appears token-by-token, thinking collapsed, tool calls shown
11. **Frontend**: Test regenerate + variant selector + continue flow
12. **Frontend**: Test rewind from message bubble
13. **Frontend**: Test stats panel updates after each turn
