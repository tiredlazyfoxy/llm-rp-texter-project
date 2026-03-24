export interface TranslationSettings {
  translate_model_id: string | null;
  translate_temperature: number;
  translate_top_p: number;
  translate_repeat_penalty: number;
  translate_think: boolean;
}
