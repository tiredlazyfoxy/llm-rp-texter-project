export interface LlmServerItem {
  id: string;
  name: string;
  backend_type: string;
  base_url: string;
  has_api_key: boolean;
  enabled_models: string[];
  is_active: boolean;
  created_at: string | null;
  modified_at: string | null;
}

export interface LlmServersListResponse {
  items: LlmServerItem[];
}

export interface CreateLlmServerRequest {
  name: string;
  backend_type: string;
  base_url: string;
  api_key?: string | null;
  is_active?: boolean;
}

export interface UpdateLlmServerRequest {
  name?: string;
  backend_type?: string;
  base_url?: string;
  api_key?: string | null;
  is_active?: boolean;
}

export interface EnabledModelInfo {
  server_id: string;
  server_name: string;
  model_id: string;
}

export interface AvailableModelsResponse {
  models: string[];
}

export interface EnabledModelsListResponse {
  models: EnabledModelInfo[];
}
