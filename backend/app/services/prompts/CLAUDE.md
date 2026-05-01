# services/prompts/

LLM prompt package — one documented file per prompt, stage-4 docstring.

```
prompts/
  placeholder_registry.py     — Static registry of prompt placeholders ({WORLD_NAME}, {RULES}, {DECISION}, …)
  tool_catalog.py             — Static registry of tools with name, description, category (research/action/planning/director)
  default_templates.py        — Default prompt templates (simple, tool, writer, director) using {PLACEHOLDER} syntax
  world_field_editor_system_prompt.py — System prompt for LLM-assisted field editing; also hosts `build_pipeline_prompt_editor_system()`, the world-agnostic builder used by the pipeline-prompt editor
  planning_system_prompt.py   — Planning stage system prompt (chain mode, legacy fallback)
  writing_system_prompt.py    — Writing stage system prompt (chain mode, legacy fallback)
  writing_plan_message.py     — Plan injection template for writer
```
