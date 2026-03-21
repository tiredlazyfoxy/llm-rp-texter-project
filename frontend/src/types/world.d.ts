// ── Worlds ──────────────────────────────────────────────────────

export interface WorldItem {
  id: string;
  name: string;
  description: string;
  lore: string;
  system_prompt: string;
  character_template: string;
  initial_message: string;
  pipeline: string;
  generation_mode: string;
  agent_config: string;
  status: string;
  owner_id: string | null;
  created_at: string | null;
  modified_at: string | null;
}

export interface WorldDetail extends WorldItem {
  stats: StatDefinitionItem[];
  rules: RuleItem[];
  location_count: number;
  npc_count: number;
  lore_fact_count: number;
}

export interface WorldsListResponse {
  items: WorldItem[];
}

export interface CreateWorldRequest {
  name: string;
  description?: string;
  status?: string;
}

export interface UpdateWorldRequest {
  name?: string;
  description?: string;
  lore?: string;
  system_prompt?: string;
  character_template?: string;
  initial_message?: string;
  pipeline?: string;
  generation_mode?: string;
  agent_config?: string;
  status?: string;
}

// ── Pipeline ───────────────────────────────────────────────────

export interface PipelineStage {
  step_type: string;
  prompt: string;
  max_agent_steps: number | null;
}

export interface PipelineConfig {
  stages: PipelineStage[];
}

// ── Documents ───────────────────────────────────────────────────

export interface NpcLinkInfo {
  link_id: string;
  location_id: string;
  location_name: string;
  link_type: string;
}

export interface LinkedNpcInfo {
  link_id: string;
  npc_id: string;
  npc_name: string;
  link_type: string;
}

export interface DocumentItem {
  id: string;
  doc_type: string;
  world_id: string;
  name: string | null;
  content: string;
  created_at: string | null;
  modified_at: string | null;
  exits: string[] | null;
  links: NpcLinkInfo[] | null;
  linked_npcs: LinkedNpcInfo[] | null;
  is_injected: boolean;
  weight: number;
}

export interface DocumentSaveResponse extends DocumentItem {
  embedding_warning: string | null;
}

export interface DocumentsListResponse {
  items: DocumentItem[];
}

export interface CreateDocumentRequest {
  doc_type: string;
  name?: string;
  content: string;
  exits?: string[];
}

export interface UpdateDocumentRequest {
  name?: string;
  content?: string;
  exits?: string[];
  is_injected?: boolean;
  weight?: number;
}

// ── Stats ───────────────────────────────────────────────────────

export interface StatDefinitionItem {
  id: string;
  world_id: string;
  name: string;
  description: string;
  scope: string;
  stat_type: string;
  default_value: string;
  min_value: number | null;
  max_value: number | null;
  enum_values: string[] | null;
  hidden: boolean;
}

export interface CreateStatRequest {
  name: string;
  description?: string;
  scope: string;
  stat_type: string;
  default_value?: string;
  min_value?: number;
  max_value?: number;
  enum_values?: string[];
  hidden?: boolean;
}

export interface UpdateStatRequest {
  name?: string;
  description?: string;
  scope?: string;
  stat_type?: string;
  default_value?: string;
  min_value?: number | null;
  max_value?: number | null;
  enum_values?: string[] | null;
  hidden?: boolean | null;
}

// ── Rules ───────────────────────────────────────────────────────

export interface RuleItem {
  id: string;
  world_id: string;
  rule_text: string;
  order: number;
}

export interface CreateRuleRequest {
  rule_text: string;
  order?: number;
}

export interface UpdateRuleRequest {
  rule_text?: string;
  order?: number;
}

// ── NPC-Location Links ──────────────────────────────────────────

export interface NpcLocationLinkItem {
  id: string;
  npc_id: string;
  npc_name: string;
  location_id: string;
  location_name: string;
  link_type: string;
}

export interface NpcLocationLinksListResponse {
  items: NpcLocationLinkItem[];
}

export interface CreateNpcLocationLinkRequest {
  npc_id: string;
  location_id: string;
  link_type: string;
}
