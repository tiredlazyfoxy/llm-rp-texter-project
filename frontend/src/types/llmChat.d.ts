export interface ChatMessageIn {
  role: "user" | "assistant";
  content: string;
}

export interface LlmChatRequest {
  model_id: string;
  messages: ChatMessageIn[];
  temperature: number;
  top_p: number;
  repetition_penalty: number;
  enable_thinking: boolean;
  enable_tools: boolean;
  current_content: string;
  world_id: string;
  doc_id: string;
  doc_type: string;
  field_type: string;
}

export interface ToolCallEntry {
  tool_name: string;
  arguments: Record<string, unknown>;
  result?: string;
}

export interface SSEHandlers {
  onToken?: (content: string) => void;
  onThinking?: (content: string) => void;
  onThinkingDone?: () => void;
  onToolCallStart?: (tool_name: string, arguments: Record<string, unknown>) => void;
  onToolCallResult?: (tool_name: string, result: string) => void;
  onDone?: (content: string) => void;
  onError?: (message: string) => void;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinkingContent?: string;
  toolCalls?: ToolCallEntry[];
  isStreaming?: boolean;
}

export interface TranslateRequest {
  text: string;
  model_id: string;
}

export interface TranslateResponse {
  translated_text: string;
}

export interface EditorLlmParams {
  temperature: number;
  top_p: number;
  repetition_penalty: number;
  enable_thinking: boolean;
  enable_tools: boolean;
}
