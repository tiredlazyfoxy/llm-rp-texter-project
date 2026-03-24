interface ModelConfig {
  model_id: string | null;
  temperature: number;
  repeat_penalty: number;
  top_p: number;
}

interface ChatSessionItem {
  id: string;
  world_id: string;
  world_name: string;
  character_name: string;
  current_location_name: string | null;
  current_turn: number;
  status: "active" | "archived";
  modified_at: string;
}

interface ChatSession {
  id: string;
  world_id: string;
  world_name: string;
  character_name: string;
  character_description: string;
  character_stats: Record<string, number | string | string[]>;
  world_stats: Record<string, number | string | string[]>;
  current_location_id: string | null;
  current_location_name: string | null;
  current_turn: number;
  status: "active" | "archived";
  tool_model: ModelConfig;
  text_model: ModelConfig;
  user_instructions: string;
  created_at: string;
  modified_at: string;
}

interface UpdateChatSettingsRequest {
  tool_model?: ModelConfig;
  text_model?: ModelConfig;
  user_instructions?: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  turn_number: number;
  tool_calls: ToolCallInfo[] | null;
  generation_plan: string | null;
  thinking_content: string | null;
  is_active_variant: boolean;
  created_at: string;
}

interface ToolCallInfo {
  tool_name: string;
  arguments: Record<string, string | null>;
  result: string;
}

interface GenerationPlanData {
  collected_data: string;
  decisions: string[];
  stat_updates: Array<{ name: string; value: string }>;
}

interface GenerationVariant {
  content: string;
  tool_calls: ToolCallInfo[] | null;
  generation_plan: GenerationPlanData | null;
  thinking_content: string | null;
  created_at: string;
}

interface ChatStateSnapshot {
  turn_number: number;
  location_id: string | null;
  location_name: string | null;
  character_stats: Record<string, number | string | string[]>;
  world_stats: Record<string, number | string | string[]>;
}

interface ChatDetail {
  session: ChatSession;
  messages: ChatMessage[];
  snapshots: ChatStateSnapshot[];
  variants: GenerationVariant[];
  summaries: ChatSummary[];
}

interface WorldInfo {
  id: string;
  name: string;
  description: string;
  lore: string;
  character_template: string;
  generation_mode: "simple" | "chain" | "agentic";
  locations: LocationBrief[];
  stat_definitions: StatDefinition[];
}

interface LocationBrief {
  id: string;
  name: string;
}

interface StatDefinition {
  name: string;
  description: string;
  scope: "character" | "world";
  stat_type: "int" | "enum" | "set";
  default_value: string;
  min_value: number | null;
  max_value: number | null;
  enum_values: string[] | null;
  hidden: boolean;
}

interface EditMessageRequest {
  content: string;
}

interface RegenerateRequest {
  turn_number?: number;
}

interface CreateChatRequest {
  world_id: string;
  character_name: string;
  template_variables: Record<string, string>;
  starting_location_id: string;
  tool_model: ModelConfig;
  text_model: ModelConfig;
}

interface SendMessageRequest {
  content: string;
}

interface ContinueRequest {
  variant_index: number;
}

interface RewindRequest {
  target_turn: number;
}

interface ChatSummaryItem {
  id: string;
  start_turn: number;
  end_turn: number;
  content: string;
  created_at: string;
}

interface ChatSummary {
  id: string;
  start_message_id: string;
  end_message_id: string;
  start_turn: number;
  end_turn: number;
  content: string;
  created_at: string;
}

interface CompactRequest {
  up_to_message_id: string;
}

interface CompactResponse {
  summary: ChatSummary;
  updated_message_count: number;
}

// SSE event data types
interface SSETokenEvent {
  content: string;
}

interface SSEThinkingEvent {
  content: string;
}

interface SSEToolCallStartEvent {
  tool_name: string;
  arguments: Record<string, string>;
}

interface SSEToolCallResultEvent {
  tool_name: string;
  result: string;
}

interface SSEStatUpdateEvent {
  stats: Record<string, number | string | string[]>;
}

interface SSEDoneEvent {
  message: ChatMessage;
}

interface SSEPhaseEvent {
  phase: "planning" | "writing";
}

interface SSEStatusEvent {
  text: string;
}

interface SSEErrorEvent {
  detail: string;
}
