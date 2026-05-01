# Feature 004 Step 001 — Prompt Tuning Infrastructure

## Context

With all prompts implemented across features 001– 003, this step establishes the infrastructure and workflow for iterating on prompt quality. The goal: any developer can tune any prompt without understanding the full codebase, using only the prompt file itself as context.

### Dependencies

- Feature 002 Steps 002–004 (all chat prompts implemented in prompts/ package)
- Feature 003 Step 001 (pipeline prompts implemented in prompts/ package)
- Feature 001 Step 005 (document editor prompt implemented in prompts/ package)

---

## 1. Prompt Package Structure

Established in feature 002 step 002, extended in feature 003 step 001 and feature 001 step 005.

```
backend/app/services/prompts/
    __init__.py                          # Re-exports all constants + functions
    chat_system_prompt.py                # CHAT_SYSTEM_PROMPT
    summarize_system_prompt.py           # SUMMARIZE_SYSTEM_PROMPT
    summarize_user_prompt.py             # SUMMARIZE_USER_PROMPT
    thinking_agent_system_prompt.py      # THINKING_AGENT_SYSTEM_PROMPT
    prose_writer_system_prompt.py        # PROSE_WRITER_SYSTEM_PROMPT
    prose_writer_plan_message.py         # PROSE_WRITER_PLAN_MESSAGE
    document_editor_system_prompt.py     # build_document_editor_system()
```

`__init__.py` re-exports everything. Existing imports like `from app.services.prompts import CHAT_SYSTEM_PROMPT` work unchanged — zero import changes needed anywhere.

---

## 2. Documentation Standard

Every prompt file MUST contain a module docstring with these 5 sections:

### Required Sections

1. **PURPOSE** — What this prompt is. One paragraph. What role it plays in the system.

2. **USAGE** — Exact location where this prompt is consumed:
   - Service function name and file
   - Which stage/step introduced it
   - Which agent/pipeline stage uses it
   - What calls the service function

3. **VARIABLES** — Every interpolation variable:
   - Variable name
   - Source (which DB model/field or computed value)
   - What it contains / format
   - Whether it can be empty

4. **DESIGN RATIONALE** — The core of prompt tuning knowledge:
   - Why the prompt is structured this way
   - What requirements drove specific wording
   - What was tried before and why it failed
   - Lessons learned from testing
   - Edge cases and how the prompt handles them
   - Cross-prompt dependencies (what other prompts interact with this one)

5. **CHANGELOG** — Version history of significant prompt changes:
   - Version identifier (tied to stage or tuning session)
   - What changed
   - Why it changed (what problem was observed)
   - What improved (measured or observed)

### Example File

```python
"""
SUMMARIZE_SYSTEM_PROMPT
=======================

PURPOSE
-------
System message for the summarization LLM call. Instructs the LLM to condense
a range of chat messages into a narrative summary that preserves plot-relevant
information for future context injection.

USAGE
-----
- Service: summarization_service.py :: compact_messages(), regenerate_summary()
- Stage: Feature 002 Step 004 (Summarization)
- Agent: Standalone summarization call (non-streaming, no tools)
- Called when: User clicks "Compact" on an assistant message, or regenerates a summary

VARIABLES
---------
- {character_name} -- ChatSession.character_name. The player character's name.
  Used so the summary refers to the character by name in third person.
  Never empty (required at session creation).

DESIGN RATIONALE
----------------
- Third person past tense chosen because summaries are injected as system
  messages (narrator voice), not as dialogue. First-person was tested and
  caused the LLM to confuse summary content with new player actions.
- "Factual and comprehensive" instruction added after testing showed the LLM
  would sometimes editorialize or add dramatic flair to summaries, which
  then influenced the tone of subsequent generations.
- Character name is explicitly required in the prompt rather than letting the
  LLM infer it from message content, because in early testing the LLM
  sometimes used "the player" or "the adventurer" inconsistently.
- Cross-dependency: output of this prompt is consumed by build_chat_context()
  in chat_service.py, which injects summaries as system messages. The summary
  format must be plain narrative text (no special markers or JSON).

CHANGELOG
---------
- v1 (feature 002 step 004): Initial version.
"""

SUMMARIZE_SYSTEM_PROMPT = """\
You are a summarizer for an RPG chat session. Condense the following conversation \
into a concise narrative summary ...
"""
```

### Key Design Decisions

- **Module docstring, not comments**: First-class Python object, introspectable, renders in IDEs.
- **All 5 sections mandatory**: Even if CHANGELOG starts with just "v1: Initial version."
- **DESIGN RATIONALE is the core**: This section grows over time as tuning happens. Failed approaches and negative knowledge are especially valuable.
- **No companion files**: Everything in the `.py` file itself. One file = one prompt + all its context.
- **For builder functions** (like `build_document_editor_system()`): Same 5 sections, but VARIABLES describes function parameters instead of `{interpolation}` variables.

---

## 3. Prompt Tuning Workflow

### 3a. The Tuning Loop

1. **Identify a problem** — Observe LLM output that is incorrect, inconsistent, or low quality. Document the specific failure mode.

2. **Read the prompt file** — The file is self-sufficient. Read DESIGN RATIONALE to understand why the prompt is the way it is. Check CHANGELOG to see if this problem was addressed before.

3. **Hypothesize a fix** — Based on the documented rationale and the observed failure, draft a prompt change.

4. **Test the change** — Use the testing methodology below.

5. **Document the result** — Whether it worked or not, add to DESIGN RATIONALE (what was learned) and CHANGELOG (what changed and why).

6. **Commit** — The prompt file change + documentation update is a single commit.

### 3b. Testing Methodology

Testing prompts requires observing LLM behavior across multiple scenarios. There is no automated test suite for prompt quality — it is inherently qualitative.

**Manual testing via the running application:**

1. Set up a test world with known content (locations, NPCs, rules, stats). This world should exercise edge cases: NPCs at boundaries, stats near min/max, rules that conflict, locations with many/few exits.

2. Run several chat sessions with the modified prompt. Test:
   - Normal conversation flow (5–10 turns)
   - Edge cases relevant to the specific prompt change
   - Regeneration (does the prompt produce consistent quality?)
   - Different LLM models (if available) — prompts should be model-agnostic

3. Compare output quality against the previous prompt version.

**What to look for per prompt:**

| Prompt | Key quality signals |
|---|---|
| CHAT_SYSTEM_PROMPT | Stays in character, uses NPC names correctly, respects rules, stat updates are valid and reasonable |
| SUMMARIZE_SYSTEM_PROMPT | Summary is factual, preserves all plot points, no editorializing, correct tense/person |
| SUMMARIZE_USER_PROMPT | Messages formatted clearly enough for LLM to parse |
| THINKING_AGENT_SYSTEM_PROMPT | JSON output is valid, tool calls are purposeful (not redundant), decisions are logical |
| PROSE_WRITER_SYSTEM_PROMPT | Prose is immersive, follows plan faithfully, no meta-information leaks |
| PROSE_WRITER_PLAN_MESSAGE | Plan is presented clearly enough that writer follows it |
| document_editor_system_prompt | Generated content matches world tone, is usable as document text |

**Debug logging:**

All prompt interpolation happens in service functions that log at DEBUG level. To inspect the exact prompt sent to the LLM:

```bash
LOG_LEVEL=DEBUG uvicorn app.main:app --port 8085 --reload
```

### 3c. Comparing Prompt Versions

When making a prompt change:

1. Save the current prompt output for 3–5 test scenarios (copy assistant messages from chat UI or DEBUG logs).
2. Apply the prompt change.
3. Regenerate responses for the same scenarios (use regenerate feature or start fresh sessions with same inputs).
4. Compare outputs side-by-side. Document observations in DESIGN RATIONALE.

No A/B testing infrastructure. Comparison is manual and qualitative. The project is small enough that manual review is more effective than automated metrics for narrative quality.

---

## 4. Documentation Maintenance Process

### 4a. When to Update Documentation

Documentation in prompt files MUST be updated when:

- The prompt text changes (any change, no matter how small)
- A new variable is added or removed
- The prompt is used in a new location (USAGE section)
- A tuning session reveals new design rationale (even if prompt doesn't change)
- A failed experiment provides useful negative knowledge

### 4b. Negative Knowledge is Valuable

The DESIGN RATIONALE section should document what DIDN'T work, not just what does. Examples:

- "Tried instructing the LLM to output JSON stat updates instead of the [STAT_UPDATE] block format. Failed because LLMs frequently broke JSON syntax when appending it to prose. Reverted to simple key=value format."
- "Attempted to reduce prompt length by summarizing stat definitions instead of listing them fully. LLM then hallucinated stat constraints (inventing min/max values). Full definitions are necessary."

This prevents future tuners from repeating failed experiments.

### 4c. Cross-Prompt Dependencies

Some prompts interact with each other. When tuning one prompt in a pair:

- Note the dependency in both files' DESIGN RATIONALE
- Test both prompts together after changes to either
- Document the interaction pattern (what format does prompt A produce that prompt B expects?)

Known cross-prompt dependencies:

| Producer | Consumer | Contract |
|---|---|---|
| THINKING_AGENT_SYSTEM_PROMPT | PROSE_WRITER_PLAN_MESSAGE | JSON GenerationPlanOutput schema (collected_data, stat_updates, decisions) |
| CHAT_SYSTEM_PROMPT | parse_stat_updates() in chat_tools.py | `[STAT_UPDATE]...[/STAT_UPDATE]` block format |
| SUMMARIZE_SYSTEM_PROMPT + SUMMARIZE_USER_PROMPT | build_chat_context() in chat_service.py | Summary text injected as system message |

---

## 5. Validation Checklist

When implementing or reviewing prompt files, verify:

- [ ] Module docstring present with all 5 required sections (PURPOSE, USAGE, VARIABLES, DESIGN RATIONALE, CHANGELOG)
- [ ] PURPOSE is one clear paragraph
- [ ] USAGE lists exact file, function, stage, and caller
- [ ] VARIABLES lists every `{variable}` with source and format
- [ ] DESIGN RATIONALE explains at least one "why" decision
- [ ] CHANGELOG has at least "v1" entry
- [ ] Prompt constant is the only export from the file (besides the module docstring)
- [ ] `__init__.py` re-exports the constant/function
- [ ] All existing imports (`from app.services.prompts import X`) still work
- [ ] Cross-prompt dependencies are documented in both files of each pair

---

## New Files

None — this plan defines standards applied during feature 002 and feature 003 implementation. The folder structure and documentation requirements are incorporated into those plans directly.

---

## Verification

1. All 7 prompt files exist in `backend/app/services/prompts/` with complete documentation headers
2. `from app.services.prompts import CHAT_SYSTEM_PROMPT` works (and all other constants/functions)
3. Each prompt file is self-sufficient: a developer can read just that file and understand what to change, why, and how to test
4. DESIGN RATIONALE sections contain actual rationale (not placeholder text)
5. CHANGELOG sections are maintained as prompts are tuned
6. Cross-prompt dependencies are documented in both files of each pair
