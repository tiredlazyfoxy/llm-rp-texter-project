# Stage 3 Step 3b — Frontend: Debug Mode, SSE Phase/Status, Message Management UI

## Context

Step 3a adds backend support (thinking_content storage, edit/delete endpoints, regenerate with turn_number). This sub-step adapts the frontend to use those backends and adds: debug mode toggle, SSE phase/status handling, status indicator during generation, debug panels on messages, message edit/delete UI, and hidden stats filtering.

### Dependencies

- Stage 3 Step 3a (thinking_content on messages, edit/delete endpoints, regenerate with turn_number)
- Stage 3 Step 2a/2b (backend SSE events already emitting phase/status)

---

## 1. TypeScript Type Updates — `frontend/src/types/chat.d.ts`

### 1a. ChatMessage — Add Fields

```typescript
// Add to existing ChatMessage interface
generation_plan: string | null;       // JSON string of GenerationPlanOutput (chain mode)
thinking_content: string | null;      // stored thinking/reasoning content
```

### 1b. WorldInfo — Add generation_mode

```typescript
// Add to existing WorldInfo interface
generation_mode: "simple" | "chain" | "agentic";
```

### 1c. StatDefinition — Add hidden

```typescript
// Add to existing StatDefinition interface
hidden: boolean;
```

### 1d. New SSE Event Types

```typescript
interface SSEPhaseEvent {
    phase: "planning" | "writing";
}

interface SSEStatusEvent {
    text: string;
}
```

### 1e. New Request Types

```typescript
interface EditMessageRequest {
    content: string;
}

interface RegenerateRequest {
    turn_number?: number;
}
```

---

## 2. SSE Handler Additions — `frontend/src/api/chat.ts`

### 2a. ChatSSEHandlers Interface

Add to existing interface:

```typescript
onPhase?: (phase: "planning" | "writing") => void;
onStatus?: (text: string) => void;
```

### 2b. Stream Parser — `_streamChat()`

Add cases to the event switch:

```typescript
case "phase":
    handlers.onPhase?.(parsed.phase);
    break;
case "status":
    handlers.onStatus?.(parsed.text);
    break;
```

### 2c. New API Functions

```typescript
export async function editMessage(chatId: string, messageId: string, content: string): Promise<ChatDetail> {
    // PUT /api/chats/{chatId}/messages/{messageId}
}

export async function deleteMessage(chatId: string, messageId: string): Promise<ChatDetail> {
    // DELETE /api/chats/{chatId}/messages/{messageId}
}
```

### 2d. Update regenerateMessage()

Accept optional `turn_number` parameter, send as JSON body if provided.

---

## 3. ChatStore Updates — `frontend/src/user/stores/ChatStore.ts`

### 3a. New Observables

```typescript
debugMode: boolean = false;                           // persisted to localStorage
currentPhase: "planning" | "writing" | null = null;   // reset on done
currentStatus: string | null = null;                  // reset on done
```

### 3b. Debug Mode Actions

```typescript
toggleDebugMode(): void {
    this.debugMode = !this.debugMode;
    localStorage.setItem("chatDebugMode", String(this.debugMode));
}
```

Load from localStorage in constructor/init: `this.debugMode = localStorage.getItem("chatDebugMode") === "true"`.

### 3c. SSE Wiring — sendMessage() and regenerate()

Add to SSE handler objects:

```typescript
onPhase: action((phase) => { this.currentPhase = phase; }),
onStatus: action((text) => { this.currentStatus = text; }),
```

On `done` callback: reset `this.currentPhase = null`, `this.currentStatus = null`.

### 3d. Message Management Actions

```typescript
async editMessage(messageId: string, newContent: string): Promise<void> {
    // Call API editMessage(), then reload chat detail
    // After reload, call sendMessage(newContent) to re-generate
}

async deleteMessage(messageId: string): Promise<void> {
    // Call API deleteMessage(), then reload chat detail
}

async regenerateAtTurn(turnNumber: number): Promise<void> {
    // Call regenerate with turn_number param
}
```

---

## 4. Status Indicator — `frontend/src/user/components/ChatInput.tsx`

When `isSending === true`:

- If `currentStatus` is non-null: show animated status text below/near the input area
- Spinner/pulsing dot + status text (e.g., "Gathering context...")
- If `currentPhase` is set: show phase badge (`[Planning]` or `[Writing]`)
- Falls back to existing loading indicator when no status text

---

## 5. Debug Mode Toggle — `frontend/src/user/components/ChatSettingsPanel.tsx`

Add at bottom of settings drawer:

- Only visible when user role is `editor` or `admin`
- Mantine `Switch` component: "Debug mode"
- Description: "Show detailed generation info (tool calls, thinking, plans)"
- Bound to `chatStore.debugMode` / `chatStore.toggleDebugMode()`

---

## 6. Debug Panels on Messages — `frontend/src/user/components/MessageBubble.tsx`

For assistant messages, when `debugMode` is ON:

### 6a. Tool Calls — Enhanced ToolCallTrace

- Pass `debugMode` prop to `ToolCallTrace`
- When debug: remove 200-char truncation, show full result in scrollable monospace area
- Show arguments as formatted/indented JSON
- Each tool call collapsible individually

### 6b. Thinking Content

- If `message.thinking_content` is non-null (loaded messages) or `streamingThinking` exists (streaming):
  - Collapsible "Thinking" section, collapsed by default
  - Monospace text display
- Only shown when debugMode is ON

### 6c. Generation Plan (chain mode)

- If `message.generation_plan` is non-null:
  - Parse JSON string to object
  - Collapsible "Generation Plan" section
  - Sub-sections: Collected Data (text block), Decisions (bullet list), Stat Updates (table name → value)
- Only shown when debugMode is ON

### 6d. When Debug Mode OFF

- Render message content only (current clean behavior)
- Hide tool calls, thinking, generation plan
- Thinking shown during streaming is OK (existing behavior) — but hidden after message is loaded

---

## 7. Message Edit/Delete UI — `frontend/src/user/components/MessageBubble.tsx`

### 7a. Action Buttons (hover/focus)

On non-summarized, non-system messages, show action icon buttons:

- **User messages**: Edit (pencil), Delete (trash)
- **Assistant messages**: Regenerate (refresh), Delete (trash)
- Show on hover/focus, small subtle icons

### 7b. Edit Flow

- Click edit → message content replaced with inline `Textarea` (pre-filled)
- Two buttons below: "Save & Resend" (primary) + "Cancel" (subtle)
- "Save & Resend" calls `chatStore.editMessage(messageId, newContent)`
- Store action: calls API edit → reloads chat → calls sendMessage to re-generate

### 7c. Delete Flow

- Click delete → confirmation dialog ("Delete this message?")
- On confirm → `chatStore.deleteMessage(messageId)`
- Store action: calls API delete → reloads chat detail

### 7d. Regenerate Past Turn

- On non-summarized assistant messages: refresh icon
- If latest turn: existing `chatStore.regenerate()`
- If past turn: `chatStore.regenerateAtTurn(turnNumber)`

---

## 8. Hidden Stats — `frontend/src/user/components/StatsPanel.tsx`

### 8a. Default Behavior

Filter out stats where matching `StatDefinition.hidden === true`. Need stat definitions from world info (already loaded in chat detail).

### 8b. Debug Mode Reveal

When `chatStore.debugMode === true` AND user is editor+:
- Show all stats including hidden ones
- Hidden stats rendered with dimmed opacity or small "hidden" badge
- Visual distinction so editors know which stats players can't see

---

## 9. ToolCallTrace Updates — `frontend/src/user/components/ToolCallTrace.tsx`

### 9a. Debug Mode Prop

Accept `debugMode: boolean` prop.

### 9b. Conditional Truncation

- When `debugMode === false`: keep existing 200-char truncation on result text
- When `debugMode === true`: show full result text, no truncation
- Full result in scrollable `<pre>` or `Code` block (max-height with scroll)
- Arguments shown as formatted JSON (`JSON.stringify(args, null, 2)`)

---

## 10. Files Summary

| File | Change |
| ---- | ---- |
| `frontend/src/types/chat.d.ts` | `generation_plan`, `thinking_content` on ChatMessage; `generation_mode` on WorldInfo; `hidden` on StatDefinition; SSE phase/status types; `EditMessageRequest`, `RegenerateRequest` |
| `frontend/src/api/chat.ts` | `editMessage()`, `deleteMessage()`, `onPhase`/`onStatus` SSE handlers, regenerate with `turn_number` |
| `frontend/src/user/stores/ChatStore.ts` | `debugMode`, `currentPhase`, `currentStatus`, `toggleDebugMode()`, `editMessage()`, `deleteMessage()`, `regenerateAtTurn()` |
| `frontend/src/user/components/ChatInput.tsx` | Status indicator with animated text + phase badge during generation |
| `frontend/src/user/components/MessageBubble.tsx` | Debug panels (thinking, generation plan, enhanced tool calls), edit/delete/regenerate action buttons, inline edit textarea |
| `frontend/src/user/components/ChatSettingsPanel.tsx` | Debug mode toggle switch (editor+ only) |
| `frontend/src/user/components/StatsPanel.tsx` | Hidden stat filtering + debug mode reveal |
| `frontend/src/user/components/ToolCallTrace.tsx` | `debugMode` prop, conditional truncation, formatted JSON args |

---

## 11. Verification

1. **SSE phase/status**: during chain mode generation, `currentPhase` transitions through planning → writing, `currentStatus` shows progress text
2. **Status indicator**: animated status text appears in ChatInput area during generation, disappears on done
3. **Debug toggle**: visible only for editor+ in settings drawer, persists to localStorage
4. **Debug OFF**: clean messages, no tool/thinking/plan details on loaded messages
5. **Debug ON**: collapsible panels for tool calls (full args + results), thinking content, generation plan
6. **Hidden stats**: filtered in StatsPanel by default, visible with "hidden" badge in debug mode
7. **Edit message**: pencil icon on user messages → inline textarea → Save & Resend deletes forward + re-generates
8. **Delete message**: trash icon → confirmation → deletes + adjusts state
9. **Regenerate past turn**: refresh icon on any non-summarized assistant message → rewinds + regenerates
10. **All generation modes**: UI works correctly for both simple and chain mode
11. **Summarize any message**: "Summarize up to here" works on any non-summarized assistant message from past turns (verify existing)
12. **Unwrap summary**: expand shows original messages inline, collapse hides them (verify existing)
13. **Re-summarize**: regenerate summary button re-runs LLM, updates content (verify existing)
14. **Delete summary**: permanently unwraps messages, summary disappears (verify existing)
