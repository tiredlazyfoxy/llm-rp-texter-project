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
  current_content: string;
  world_id: string;
  doc_id: string;
  doc_type: "location" | "npc" | "lore_fact";
}

export interface SSEHandlers {
  onToken?: (content: string) => void;
  onThinking?: (content: string) => void;
  onThinkingDone?: () => void;
  onDone?: (content: string) => void;
  onError?: (message: string) => void;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinkingContent?: string;
  isStreaming?: boolean;
}

export interface EditorLlmParams {
  temperature: number;
  top_p: number;
  repetition_penalty: number;
  enable_thinking: boolean;
}
