# Stage 3 Step 3 — User UI Adaptation for Pipeline

## Context

The pipeline backend is fully functional from step 2. This step adapts the user-facing frontend to show pipeline status during generation, display generation details for editors, add per-session pipeline settings, and filter hidden stats.

### Dependencies

- Stage 3 Step 2 (pipeline backend, SSE events, API endpoints)

---

## 1. TypeScript Types

### 1a. Pipeline Types

Add to `frontend/src/types/chat.d.ts`:

```typescript
interface PipelineStageConfig {
    llm_model_id: string | null;
    temperature: number | null;
}

interface ThinkingStageConfig extends PipelineStageConfig {
    max_tool_loops: number;
}

interface PipelineConfig {
    enabled: boolean;
    thinking: ThinkingStageConfig;
    writing: PipelineStageConfig;
}

interface UpdatePipelineRequest {
    pipeline_enabled?: boolean | null;
    thinking_model_id?: string | null;
    thinking_temperature?: number | null;
    writing_model_id?: string | null;
    writing_temperature?: number | null;
}

interface GenerationPlan {
    collected_data: string;
    stat_updates: Array<{ name: string; value: string }>;
    decisions: string[];
}
```

### 1b. SSE Event Types

```typescript
interface SSEPhaseEvent {
    phase: "thinking" | "writing";
}

interface SSEStatusEvent {
    text: string;
}
```

### 1c. Updated Interfaces

- `ChatSession` — add: `pipeline_enabled`, `thinking_model_id`, `thinking_temperature`, `writing_model_id`, `writing_temperature`, `effective_pipeline: PipelineConfig`
- `ChatMessage` — add: `generation_plan: GenerationPlan | null`

---

## 2. SSE Handling

### 2a. Handler Types

Add to `ChatSSEHandlers` (or equivalent):

```typescript
onPhase?: (phase: "thinking" | "writing") => void;
onStatus?: (text: string) => void;
```

### 2b. Stream Parser

In `_streamChat` (or equivalent SSE streaming function in `frontend/src/api/chat.ts`):

- Handle `event: phase` → parse data, call `onPhase`
- Handle `event: status` → parse data, call `onStatus`

---

## 3. MobX Store

### 3a. ChatStore Additions

```typescript
// Observables
currentPhase: "thinking" | "writing" | null = null;
currentStatus: string | null = null;

// Actions
updatePipeline(req: UpdatePipelineRequest): Promise<void>
```

### 3b. SSE Wiring

In `sendMessage()` and `regenerate()`:

```typescript
onPhase: (phase) => runInAction(() => { this.currentPhase = phase; }),
onStatus: (text) => runInAction(() => { this.currentStatus = text; }),
```

On `done`: reset `currentPhase = null`, `currentStatus = null`.

---

## 4. UI Components

### 4a. Status Indicator (`ChatInput.tsx`)

During generation (`isSending === true`):
- Show `currentStatus` text if available (e.g., "Gathering context...", "Planning response...", "Writing...")
- Falls back to existing loading indicator when no status text
- Animate/pulse the status text

### 4b. Generation Details Panel (`MessageBubble.tsx`)

For assistant messages with `generation_plan` (editor+ only):

- Collapsible section: "Generation Details"
- When expanded, show:
  - **Tool Calls**: existing ToolCallTrace components (already rendered)
  - **Collected Data**: formatted text from `generation_plan.collected_data`
  - **Decisions**: bullet list from `generation_plan.decisions`
  - **Stat Updates**: table of `generation_plan.stat_updates` (name → value)
- Only visible to editor+ users (check user role from auth context)
- Collapsed by default

### 4c. Pipeline Settings (`ChatSettingsPanel.tsx`)

When the world has pipeline enabled (`effective_pipeline.enabled`):

- **Pipeline section** header
- **Toggle**: "Enable pipeline" (editor+ only) — calls `updatePipeline({ pipeline_enabled })`
- **Thinking stage**:
  - Model picker dropdown (editor+ only)
  - Temperature slider (all users)
- **Writing stage**:
  - Model picker dropdown (editor+ only)
  - Temperature slider (all users)

When pipeline is disabled: show existing single model picker + temperature.

### 4d. Hidden Stats (`StatsPanel.tsx`)

- Filter out stats where the matching `StatDefinition` has `hidden === true`
- **Debug toggle** (editor+ only): "Show hidden stats" checkbox
  - When on: show all stats, hidden ones with a visual indicator (dimmed or tagged)
  - When off: hide hidden stats completely
- Stat definitions available from world info (already loaded in chat detail)

---

## 5. Visibility Rules Summary

| Event/Data | Regular User | Editor+ (debug off) | Editor+ (debug on) |
| ---- | ---- | ---- | ---- |
| `status` text | Visible | Visible | Visible |
| `phase` transition | Used for UI state | Used for UI state | Used for UI state |
| `thinking` tokens | Hidden | Hidden | Visible |
| `tool_call_start/result` | Hidden | Hidden | Visible |
| Generation plan on message | Hidden | Hidden | Visible |
| Hidden stats | Hidden | Hidden | Visible |

Note: Backend already filters events based on role (step 2). Frontend just needs to handle whatever events arrive + role-based UI visibility for stored data (generation_plan, hidden stats).

---

## 6. Files to Modify

| File | Change |
| ---- | ---- |
| `frontend/src/types/chat.d.ts` | Pipeline types, SSE events, updated ChatSession + ChatMessage |
| `frontend/src/api/chat.ts` | `updatePipeline()`, `onPhase`/`onStatus` in SSE handlers |
| `frontend/src/user/stores/ChatStore.ts` | `currentPhase`, `currentStatus`, `updatePipeline()`, SSE wiring |
| `frontend/src/user/components/ChatInput.tsx` | Status indicator during generation |
| `frontend/src/user/components/MessageBubble.tsx` | Collapsible generation details panel (editor+) |
| `frontend/src/user/components/ChatSettingsPanel.tsx` | Pipeline settings section |
| `frontend/src/user/components/StatsPanel.tsx` | Hidden stat filtering + debug toggle (editor+) |

---

## 7. Verification

1. **Status indicator**: during pipeline generation, ChatInput area shows status text that updates through phases ("Gathering context..." → "Planning response..." → "Writing...")
2. **Regular user**: sees only status text, no thinking tokens or tool calls
3. **Editor+ debug**: sees generation details panel on assistant messages (tool calls, collected data, decisions)
4. **Pipeline settings**: editor+ can toggle pipeline, change models per stage. Regular users can adjust temperatures only.
5. **Hidden stats**: not shown in StatsPanel for regular users. Editor+ debug toggle reveals them.
6. **Regeneration**: status indicator works correctly on regenerate. Generation details show on new variant.
7. **Rewind**: rewound messages with generation_plan handled correctly (deleted, not displayed)
8. **No pipeline**: when pipeline disabled, UI behaves exactly as before (no pipeline section, no status indicator changes)
