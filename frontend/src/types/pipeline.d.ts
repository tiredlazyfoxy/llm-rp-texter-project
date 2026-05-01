// ── Pipeline ────────────────────────────────────────────────────

export interface PipelineItem {
  id: string;
  name: string;
  description: string;
  kind: string;                 // "simple" | "chain" | "agentic"
  system_prompt: string;
  simple_tools: string;         // JSON list
  pipeline_config: string;      // JSON PipelineConfig
  agent_config: string;
  created_at: string | null;
  modified_at: string | null;
}

export interface PipelinesListResponse {
  items: PipelineItem[];
}

export interface CreatePipelineRequest {
  name: string;
  description?: string;
  kind?: string;
  system_prompt?: string;
  simple_tools?: string;
  pipeline_config?: string;
  agent_config?: string;
}

export interface UpdatePipelineRequest {
  name?: string;
  description?: string;
  kind?: string;
  system_prompt?: string;
  simple_tools?: string;
  pipeline_config?: string;
  agent_config?: string;
}

// ── Pipeline shape (chain mode stages) ──────────────────────────

export interface PipelineStage {
  step_type: string;
  name: string;
  prompt: string;
  max_agent_steps: number | null;
  tools: string[];
  enabled: boolean;
  model_id: string | null;
}

export interface PipelineConfig {
  stages: PipelineStage[];
}

// ── Static pipeline-config options (placeholders, tools, templates) ─

export interface PlaceholderInfo {
  name: string;
  description: string;
  category: string;
}

export interface ToolCatalogEntry {
  name: string;
  description: string;
  category: string;
}

export interface DefaultTemplates {
  simple: string;
  tool: string;
  writer: string;
  director: string;
}

export interface PipelineConfigOptions {
  placeholders: PlaceholderInfo[];
  tools: ToolCatalogEntry[];
  default_templates: DefaultTemplates;
}
