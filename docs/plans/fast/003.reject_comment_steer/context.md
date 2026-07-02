# Fast feature 003 — reject_comment_steer — context

Follow-up bug fix on feature 014 (`chat_preference_tuning`). Chain-mode only.

## The bug

When a user rejects a chain-mode generation **with a comment**, the reject is
always `scope="plan"` (whole-chain redo). The comment is persisted to a
`ChatGenerationFeedback` row and then **dropped** — it never reaches the
immediate re-generation that follows the reject. Its only consumer today is
`retune_service`, which reads it on the **next accept**. So the comment tunes
future turns but does **not** steer the immediate re-plan / re-write the user is
waiting on. This feature threads the comment into that immediate whole-chain
redo.

## Resolved design decisions (do NOT re-litigate)

1. **Reuse the existing `{USER_INSTRUCTIONS}` channel.** Do NOT add a new
   placeholder, registry entry, or template token. On the re-run, the reject
   comment (framed as feedback) is merged into the `user_instructions` string
   that already flows through the chain. No new injection path.
2. **Steer the whole chain.** The merged instruction must reach both the
   planning (tool) stage and the writer stage. Because `user_instructions`
   already flows to both via `_build_placeholder_values` →
   `{USER_INSTRUCTIONS}`, a single merge at the top of the regenerate flow
   covers both stages. No signature change to `_run_chain_generation` is
   required — the merge happens upstream into the existing string.
3. **Fast track, chain mode only.** Simple mode
   (`chat_agent_service.regenerate_response`) already discards scope/comment and
   is explicitly out of scope.
4. **Whitespace/None safety.** A `None`, empty, or whitespace-only comment
   leaves `user_instructions` unchanged (no empty framing appended).

## Files involved (from harvester — authoritative)

All backend paths under `backend/app/`.

- **`services/chain_generation_service.py`**
  - `regenerate_chain_response(session_id, user_id, caller_role, pipeline, scope=None, comment=None)` — lines ~872–1006. `comment` is currently used ONLY at the feedback write (`ChatGenerationFeedback(... comment=comment ...)`, ~905–919, comment at 915) and never again.
  - Re-run reloads the user message and sets `user_instructions = user_msg.user_instructions` at ~line 936 (the OOC `(( ))` per-turn instructions).
  - `_run_chain_generation(...)` called at ~978–985 with `user_instructions=user_instructions`; `writer_only`/`prior_plan` derived from scope at ~968–974. `comment` is NOT passed today.
  - `_run_chain_generation(...)` signature ~658–670 threads `user_instructions` into `_run_tool_stage` and `_run_writer_stage`.
  - `_build_placeholder_values(...)` ~193–214 maps `user_instructions` → `{USER_INSTRUCTIONS}` (~line 207). No change needed there.
- **`prompts/placeholder_registry.py:35`** — `{USER_INSTRUCTIONS}` already registered; embedded in default tool/writer templates.
- **Framing precedent** — legacy fallbacks render user instructions under a
  `## Player Instructions` heading (`planning_system_prompt.py:209–210`,
  `writing_system_prompt.py:84–85`). The merged reject-comment string flows
  through the same `{USER_INSTRUCTIONS}` value, so it renders wherever that
  placeholder appears.

## Test harness reference

Feature-014 tests live in `backend/tests/`. `test_reject_attribution.py` builds a
chain-run harness that mocks `chain_generation_service.get_llm_client_for_model`.
That harness is available if an end-to-end assertion is wanted, but the primary,
lower-risk gate here is a pure unit test of the merge helper (no chain-run
harness needed).

## Commands

- Backend tests: `cd backend && .venv/Scripts/python -m pytest` (run from `backend/`).
- No backend static typecheck; no linter.
