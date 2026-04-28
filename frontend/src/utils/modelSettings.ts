const KEY_TOOL_MODEL = "llmrp_tool_model";
const KEY_TEXT_MODEL = "llmrp_text_model";

const DEFAULT_TOOL: ModelConfig = { model_id: null, temperature: 0.6, repeat_penalty: 1.1, top_p: 1.0 };
const DEFAULT_TEXT: ModelConfig = { model_id: null, temperature: 0.8, repeat_penalty: 1.2, top_p: 0.9 };

export function loadToolModel(): ModelConfig {
  try {
    const raw = localStorage.getItem(KEY_TOOL_MODEL);
    return raw ? (JSON.parse(raw) as ModelConfig) : { ...DEFAULT_TOOL };
  } catch {
    return { ...DEFAULT_TOOL };
  }
}

export function loadTextModel(): ModelConfig {
  try {
    const raw = localStorage.getItem(KEY_TEXT_MODEL);
    return raw ? (JSON.parse(raw) as ModelConfig) : { ...DEFAULT_TEXT };
  } catch {
    return { ...DEFAULT_TEXT };
  }
}

export function saveToolModel(m: ModelConfig): void {
  localStorage.setItem(KEY_TOOL_MODEL, JSON.stringify(m));
}

export function saveTextModel(m: ModelConfig): void {
  localStorage.setItem(KEY_TEXT_MODEL, JSON.stringify(m));
}
