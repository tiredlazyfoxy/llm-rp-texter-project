# Stage 6, Step 3: Structured JSON Tool Responses

## Problem

LLMs repeatedly call `update_stat` and `move_to_location` with identical parameters because the plain-text responses don't clearly signal that the operation succeeded. The model doesn't confidently "see" that the change is already applied, so it retries.

## Solution

Return structured JSON from these tools so the LLM gets an unambiguous machine-readable confirmation (or rejection) with full current state.

---

## 1. `update_stat` — JSON Response

### Success (value changed)

```json
{
  "status": "OK",
  "updated_stat": { "name": "health", "old_value": "100", "new_value": "85" },
  "all_stats": { "health": "85", "mana": "50", "location_mood": "tense" }
}
```

### Rejected (same value already set)

```json
{
  "status": "REJECTED",
  "reason": "Stat 'health' already has value '85'. No change needed.",
  "all_stats": { "health": "85", "mana": "50", "location_mood": "tense" }
}
```

### Error (invalid stat name)

```json
{
  "status": "ERROR",
  "reason": "Stat 'halth' is not recognized. Valid stats: health, mana, location_mood",
  "all_stats": { "health": "100", "mana": "50", "location_mood": "tense" }
}
```

### Error (invalid value)

```json
{
  "status": "ERROR",
  "reason": "Value 'abc' is invalid for 'health' (int). Expected integer in range [0, 100]",
  "all_stats": { "health": "100", "mana": "50", "location_mood": "tense" }
}
```

### Changes to `_b_update_stat` in `chat_tools.py`

1. Build `all_stats` dict by merging `char_stats` + `world_stats` at response time
2. Before applying: check if `target[name] == validated` — if so, return REJECTED
3. On success: include `old_value`, `new_value`, and full `all_stats` snapshot
4. On error: include `reason` and current `all_stats` (unchanged)
5. Return `json.dumps(response)` instead of plain text

---

## 2. `move_to_location` — JSON Response

### Success (moved)

```json
{
  "status": "OK",
  "location": {
    "name": "Town Square",
    "description": "A bustling square with a fountain...",
    "exits": ["Market Street", "Castle Road", "Harbor"],
    "npcs": [
      { "name": "Guard Captain", "brief": "A stern-looking officer..." }
    ]
  }
}
```

### Rejected (already at location)

```json
{
  "status": "REJECTED",
  "reason": "Player is already at 'Town Square'. No move needed.",
  "location": {
    "name": "Town Square",
    "description": "A bustling square with a fountain...",
    "exits": ["Market Street", "Castle Road", "Harbor"],
    "npcs": [
      { "name": "Guard Captain", "brief": "A stern-looking officer..." }
    ]
  }
}
```

### Error (not found)

```json
{
  "status": "ERROR",
  "reason": "Location 'Nonexistent Place' not found in this world."
}
```

### Changes to `move_to_location_impl` in `chat_tools.py`

1. After resolving location: check if `chat.current_location_id == location.id` — if so, return REJECTED with current location info
2. On success: return JSON with location name, description, exits list, npcs list
3. On error (not found / session not found): return JSON with ERROR status and reason
4. Return `json.dumps(response)` instead of markdown text

---

## 3. Files to Change

| File | Change |
|------|--------|
| `backend/app/services/chat_tools.py` | Update `_b_update_stat` and `move_to_location_impl` return formats |

No schema changes, no DB changes, no frontend changes. The tool results are strings passed back to the LLM — switching from plain text to JSON strings is transparent to the pipeline.

## 4. Tool Description Updates

Update the tool descriptions in `ToolSpec` definitions to tell the LLM what response format to expect:

- `update_stat`: *"Update a stat value. Returns JSON with status (OK/REJECTED/ERROR), the updated stat, and a snapshot of all current stats."*
- `move_to_location`: *"Move the player to a different location. Returns JSON with status (OK/REJECTED/ERROR) and the location details (description, exits, NPCs)."*

Also update the description in `tool_catalog.py` if it mirrors these.

## 5. Testing

- Verify that chain mode planning stage handles JSON tool results (it already treats them as opaque strings → no issue)
- Verify that simple mode tool calls handle JSON results in SSE `tool_call_result` events (also opaque strings → no issue)
- Test: update_stat with new value → OK
- Test: update_stat with same value → REJECTED
- Test: update_stat with invalid name → ERROR
- Test: update_stat with invalid value → ERROR
- Test: move_to_location to new place → OK
- Test: move_to_location to current place → REJECTED
- Test: move_to_location to nonexistent place → ERROR
