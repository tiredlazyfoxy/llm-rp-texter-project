# Stage 2 Step 2 — Prompts, Tools, and NPC Logic

## Context

Before building the chat API and UI, we need the service-layer building blocks: the prompts constants file (all LLM prompts in one place), the agent tool implementations, NPC presence logic, and stat update parsing. This step is backend-only — no API routes or frontend code.

---

## 1. Prompts Constants File

**File**: `backend/app/services/prompts.py`

All LLM prompts live in this single file. **No prompts in route or service files.** Each prompt is a documented string constant explaining when it's used, what variables get interpolated, and what the LLM is expected to produce.

### `CHAT_SYSTEM_PROMPT`

Used as the system message for every chat generation call.

Variables:
| Variable | Source |
|---|---|
| `{world_system_prompt}` | `World.system_prompt` |
| `{world_description}` | `World.description` |
| `{location_name}` | `WorldLocation.name` for current location |
| `{location_summary}` | First ~500 chars of `WorldLocation.content` (short context; full content available via tool) |
| `{npc_list}` | Names + short descriptions of NPCs at current location (one per line, first ~200 chars of content) |
| `{rules_text}` | All `WorldRule.rule_text` for this world, joined by newlines, ordered by `WorldRule.order` |
| `{character_name}` | `ChatSession.character_name` |
| `{character_description}` | `ChatSession.character_description` |
| `{character_stats_text}` | Formatted from `ChatSession.character_stats` JSON: `"stat_name: value"` per line |
| `{world_stats_text}` | Formatted from `ChatSession.world_stats` JSON: `"stat_name: value"` per line |
| `{stat_definitions_text}` | All `WorldStatDefinition` rows: `"stat_name (type, scope): description [constraints]"` per line |
| `{user_instructions}` | `ChatSession.user_instructions` — user-provided additional instructions (may be empty) |

Template:

```python
CHAT_SYSTEM_PROMPT = """\
{world_system_prompt}

== World ==
{world_description}

== Current Location ==
{location_name}: {location_summary}

== NPCs Present ==
{npc_list}

== Rules ==
{rules_text}

== Character ==
Name: {character_name}
{character_description}

== Character Stats ==
{character_stats_text}

== World Stats ==
{world_stats_text}

== Stat Definitions ==
{stat_definitions_text}
{user_instructions_block}
You are the game master for this RPG world. Respond to the player's actions and dialogue \
in character, maintaining consistency with the world, NPCs, rules, and stats above. \
When you need specific information about locations, NPCs, or world lore, use the provided tools. \
After your narrative response, if any stats should change based on what happened, \
output a stat update block at the end of your response in this exact format:

[STAT_UPDATE]
stat_name=new_value
stat_name2=new_value2
[/STAT_UPDATE]

Only include stats that actually changed. Respect min/max constraints and allowed enum/set values.
"""
```

Note: `{user_instructions_block}` is built by the formatting helper — empty string if `user_instructions` is blank, otherwise:
```
== User Instructions ==
{user_instructions}
```

### `CHAT_INITIAL_MESSAGE`

Used at chat creation for the initial narrative system message.

Variables: `{character_name}`, `{location_name}`, `{location_summary}`

```python
CHAT_INITIAL_MESSAGE = """\
*{character_name} arrives at {location_name}.*

{location_summary}
"""
```

### `SUMMARIZE_SYSTEM_PROMPT`

Used in step 4 for summarization calls.

Variables: `{character_name}`

```python
SUMMARIZE_SYSTEM_PROMPT = """\
You are a summarizer for an RPG chat session. Condense the following conversation \
into a concise narrative summary that preserves all important plot points, \
character decisions, stat changes, location changes, and NPC interactions. \
The summary should be written in past tense, third person, using the character name "{character_name}". \
Keep it factual and comprehensive — this summary will replace the original messages \
in the LLM context window for future turns.
"""
```

### `SUMMARIZE_USER_PROMPT`

Used in step 4 as the user message for summarization.

Variables: `{messages_text}`

```python
SUMMARIZE_USER_PROMPT = """\
Summarize the following conversation segment:

{messages_text}
"""
```

---

## 2. LLM Agent Tools

**File**: `backend/app/services/chat_tools.py`

Pydantic parameter schemas + async tool implementations. All tools are internal — DB queries only, no external HTTP calls.

### Tool: `get_location_info`

```python
class GetLocationInfoParams(BaseModel):
    """Parameters for retrieving full location details."""
    location_id: str  # snowflake as string
```

Implementation:
- Loads `WorldLocation` by ID, verifies `world_id` matches
- Returns JSON with: name, full content, exits (if any), list of NPCs linked to this location (name + link_type)
- Returns `{"error": "Location not found"}` if missing or wrong world

### Tool: `get_npc_info`

```python
class GetNPCInfoParams(BaseModel):
    """Parameters for retrieving full NPC details."""
    npc_id: str  # snowflake as string
```

Implementation:
- Loads `WorldNPC` by ID, verifies `world_id` matches
- Returns JSON with: name, full content, list of location links (location name + link_type)
- Returns `{"error": "NPC not found"}` if missing or wrong world

### Tool: `search`

```python
class SearchParams(BaseModel):
    """Parameters for vector search across world knowledge base."""
    query: str
    source_type: str | None = None  # "location" | "npc" | "lore_fact" | None (all types)
```

Implementation:
- Uses LanceDB vector search, filtered by `world_id` and optionally `source_type`
- Returns top-K relevant text chunks as JSON array
- Each result includes: source_type, source_id, source_name (if applicable), chunk text, similarity score

### Tool: `google_search` (STUB)

```python
class GoogleSearchParams(BaseModel):
    """Parameters for web search. Currently a stub."""
    query: str
```

Implementation:
- Returns `{"info": "Google search is not yet implemented. Please use the 'search' tool to find information within the world knowledge base instead.", "query": query}`
- Real integration deferred to a later stage

### Tool Registration Function

```python
def get_chat_tools(db: AsyncSession, world_id: int) -> tuple[list[dict], dict[str, Callable]]:
    """
    Returns (tool_definitions, tool_callables) for use with PythonLLMClient.

    tool_definitions: list of OpenAI-format tool schemas via pydantic_to_openai_tool()
    tool_callables: dict of tool_name -> async callable
    """
```

Uses `pydantic_to_openai_tool()` from PythonLLMClient to convert Pydantic schemas to OpenAI tool format.

Callables are closures capturing `db` and `world_id`:
```python
callables = {
    "get_location_info": lambda **kw: get_location_info(db=db, world_id=world_id, **kw),
    "get_npc_info": lambda **kw: get_npc_info(db=db, world_id=world_id, **kw),
    "search": lambda **kw: search(world_id=world_id, **kw),
    "google_search": lambda **kw: google_search(**kw),
}
```

---

## 3. NPC Presence Logic

**File**: `backend/app/services/chat_tools.py`

```python
async def get_npcs_at_location(world_id: int, location_id: int, db: AsyncSession) -> list[WorldNPC]:
```

Determines which NPCs can appear at a given location based on `NPCLocationLink` rules:

| NPC has... | Behavior |
|---|---|
| No links at all | Roaming — can appear anywhere |
| `present` links | Only at those specific locations |
| `excluded` links | Anywhere EXCEPT those locations |

Algorithm:
1. Load all NPCs for `world_id`
2. Load all `NPCLocationLink` rows for `world_id`
3. Group links by `npc_id`
4. For each NPC:
   - No links → include (roaming)
   - Has `present` links → include only if `location_id` is in the present set
   - Has `excluded` links → include only if `location_id` is NOT in the excluded set
5. Return matching NPCs

Used when building the prompt to populate the `{npc_list}` variable with NPCs present at the current location.

---

## 4. Stat Update Parsing

**File**: `backend/app/services/chat_tools.py`

### Parser

```python
import re

STAT_UPDATE_PATTERN = re.compile(r'\[STAT_UPDATE\]\s*(.*?)\s*\[/STAT_UPDATE\]', re.DOTALL)

def parse_stat_updates(content: str) -> tuple[str, dict[str, str]]:
    """
    Extract [STAT_UPDATE]...[/STAT_UPDATE] block from LLM response.

    Returns:
        (clean_content, updates_dict)
        - clean_content: response text with the STAT_UPDATE block removed
        - updates_dict: {"stat_name": "new_value", ...}
    """
```

Parses lines like `stat_name=new_value` from the block.

### Validator

```python
async def validate_and_apply_stat_updates(
    session: ChatSession,
    updates: dict[str, str],
    stat_definitions: list[WorldStatDefinition],
    db: AsyncSession
) -> None:
    """
    Validate stat updates against WorldStatDefinition constraints and apply to session.

    - int stats: parse as int, clamp to min/max
    - enum stats: verify value is in enum_values list
    - set stats: parse as comma-separated, verify each value is in enum_values
    - Unknown stat names are ignored (logged as warning)
    - Updates the appropriate JSON field (character_stats or world_stats) on the session
    """
```

---

## 5. Prompt Formatting Helpers

**File**: `backend/app/services/chat_tools.py`

Helper functions for building prompt variables:

```python
def format_stats_text(stats_json: str) -> str:
    """Format JSON stats string as 'stat_name: value' lines."""

def format_stat_definitions(definitions: list[WorldStatDefinition]) -> str:
    """Format stat definitions as 'name (type, scope): description [constraints]' lines."""

def format_npc_list(npcs: list[WorldNPC]) -> str:
    """Format NPCs as 'name: short_description' lines (first ~200 chars of content)."""

def get_location_summary(location: WorldLocation) -> str:
    """Return first ~500 chars of location content as a short summary."""
```

---

## New Files

| File | Purpose |
|---|---|
| `backend/app/services/prompts.py` | All LLM prompt constants with documentation |
| `backend/app/services/chat_tools.py` | Tool schemas, implementations, NPC logic, stat parsing, formatting helpers |

---

## Dependencies

- Stage 1 Step 2: World models (`World`, `WorldLocation`, `WorldNPC`, `WorldLoreFact`, `NPCLocationLink`, `WorldStatDefinition`, `WorldRule`)
- Stage 1 Step 3: LLM server management (`LlmServer`, model resolution)
- Stage 1 Step 5: LLM client utilities (`get_llm_client_for_model`)
- LanceDB vector storage (from stage 1 step 2)

---

## Verification

1. **Prompts**: Render `CHAT_SYSTEM_PROMPT` with sample world data — verify all variables interpolate correctly, output is well-structured
2. **get_location_info**: Call with valid/invalid location IDs — verify correct JSON response or error
3. **get_npc_info**: Call with valid/invalid NPC IDs — verify correct JSON response or error
4. **search**: Call with a query against a world with indexed documents — verify relevant chunks returned
5. **google_search**: Call — verify stub response returned
6. **get_npcs_at_location**: Test with:
   - NPC with no links (roaming) → appears at any location
   - NPC with `present` link to location A → appears at A, not at B
   - NPC with `excluded` link to location B → appears at A, not at B
7. **parse_stat_updates**: Test with response containing `[STAT_UPDATE]` block → verify clean content + parsed updates
8. **parse_stat_updates**: Test with response without block → verify content unchanged, empty updates
9. **validate_and_apply_stat_updates**: Test int stat clamping, enum validation, set validation, unknown stat name handling
10. **Tool registration**: Call `get_chat_tools()` — verify returns valid tool definitions and callables
