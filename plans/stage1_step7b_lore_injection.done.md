# Stage 1 Step 7b — Lore Fact Injection Control

## What Was Built

Two new fields on `WorldLoreFact`: `is_injected` (bool, default false) and `weight` (int, default 0).

- **`is_injected=True`** facts are always included in the LLM system prompt under `## World Context`, sorted by weight ascending. This applies regardless of `enable_tools` — they are foundational world facts the LLM should always have.
- **`is_injected=False`** facts are only injected when `enable_tools=False` (full lore dump for plain chat mode). With tools enabled, the LLM must fetch them actively via `search`/`get_lore`.
- Injected fact IDs are filtered from `search` and `get_lore` tool results — no need to return what is already in context.

`World.lore` (legacy blob field on the world record) is deprecated: hidden from the admin UI, no longer passed to prompts. DB field kept for backward compatibility.

## Key Design Decisions

**Two-tier lore model.** Some facts are so fundamental that the LLM should always have them (world name etymology, calendar system, magic rules, etc.). Others are background detail better fetched on demand. The `is_injected` flag makes this explicit rather than relying on prompt length heuristics.

**Weight determines injection order.** Lower weight = appears earlier in `## World Context`. Editors control which facts come first without needing to reorder records in the DB.

**Injected facts excluded from tool search.** If a fact is already in context, returning it again from a tool call wastes a round and repeats content. The `_get_injected_ids()` helper loads IDs once per tool invocation and filters them out of vector search results in both `search_impl` and `get_lore_impl`.

**`world.lore` deprecated, not removed.** The DB field stays to avoid a destructive migration. The UI simply hides it; the prompt builder ignores it. Any existing lore content can be migrated manually to `is_injected` lore facts.

## Files

- `backend/app/models/world.py` — `is_injected`, `weight` fields on `WorldLoreFact`
- `backend/app/db/lore_facts.py` — `list_injected_by_world()` sorted by weight
- `backend/app/services/db_import_export.py` — both fields serialized with backward-compat defaults
- `backend/app/models/schemas/worlds.py` — fields in `DocumentResponse` + `UpdateDocumentRequest`
- `backend/app/routes/admin/worlds.py` — `_doc_to_response()` populates both fields
- `backend/app/services/world_editor.py` — apply on update, preserve on clone
- `backend/app/routes/llm_chat.py` — always fetch injected facts; non-injected skipped when tools on
- `backend/app/services/prompts/document_editor_system_prompt.py` — `injected_lore` param → `## World Context`
- `backend/app/services/admin_tools.py` — `_get_injected_ids()` helper; filter from search/get_lore
- `frontend/src/types/world.d.ts` — `is_injected`, `weight` on `DocumentItem` + `UpdateDocumentRequest`
- `frontend/src/admin/pages/WorldViewPage.tsx` — lore tab: injected pinned at top, divider, regular below; `world.lore` display removed
- `frontend/src/admin/pages/WorldEditPage.tsx` — `world.lore` textarea removed
- `frontend/src/admin/pages/DocumentEditPage.tsx` — "Always inject" toggle + "Injection order" input for lore facts
