import { useCallback, useRef, useState } from "react";
import type { TranslateRequest } from "../types/llmChat";
import { getTranslationSettings } from "../utils/translationSettings";

export interface TranslateStreamHandlers {
  onThinking: (content: string) => void;
  onToken: (content: string) => void;
  onDone: (content: string) => void;
  onError: (message: string) => void;
}

export type TranslateStreamFn = (
  req: TranslateRequest,
  handlers: TranslateStreamHandlers,
) => AbortController;

interface UseTranslationOptions {
  getValue: () => string;
  setValue: (text: string) => void;
  translateFn: TranslateStreamFn;
}

interface UseTranslationReturn {
  isTranslating: boolean;
  canRevert: boolean;
  translateError: string | null;
  handleTranslate: () => void;
  handleRevert: () => void;
  onInputChange: (newValue: string) => void;
  clearTranslateError: () => void;
}

export function useTranslation({
  getValue,
  setValue,
  translateFn,
}: UseTranslationOptions): UseTranslationReturn {
  const [isTranslating, setIsTranslating] = useState(false);
  const [canRevert, setCanRevert] = useState(false);
  const [translateError, setTranslateError] = useState<string | null>(null);
  const originalTextRef = useRef<string | null>(null);
  const translatedTextRef = useRef<string | null>(null);
  const thinkingRef = useRef("");
  const tokenRef = useRef("");
  const gotTokenRef = useRef(false);

  const handleTranslate = useCallback(() => {
    const text = getValue().trim();
    if (!text) return;

    const settings = getTranslationSettings();
    if (!settings.translate_model_id) {
      setTranslateError("No translation model configured. Set it in Translation Settings (user menu).");
      return;
    }
    setTranslateError(null);

    originalTextRef.current = getValue();
    thinkingRef.current = "";
    tokenRef.current = "";
    gotTokenRef.current = false;
    setIsTranslating(true);

    translateFn(
      {
        text,
        model_id: settings.translate_model_id,
        temperature: settings.translate_temperature,
        top_p: settings.translate_top_p,
        repeat_penalty: settings.translate_repeat_penalty,
        enable_thinking: settings.translate_think,
      },
      {
        onThinking: (content) => {
          // Show thinking in input as visual feedback while model thinks
          thinkingRef.current += content;
          setValue(thinkingRef.current);
        },
        onToken: (content) => {
          // First real token: replace thinking text with actual translation
          if (!gotTokenRef.current) {
            gotTokenRef.current = true;
          }
          tokenRef.current += content;
          setValue(tokenRef.current);
        },
        onDone: (content) => {
          translatedTextRef.current = content;
          setValue(content);
          setIsTranslating(false);
          setCanRevert(true);
        },
        onError: (message) => {
          // Restore original on error
          if (originalTextRef.current !== null) {
            setValue(originalTextRef.current);
          }
          originalTextRef.current = null;
          translatedTextRef.current = null;
          setIsTranslating(false);
          setTranslateError(message);
        },
      },
    );
  }, [getValue, setValue, translateFn]);

  const handleRevert = useCallback(() => {
    if (originalTextRef.current !== null) {
      setValue(originalTextRef.current);
      originalTextRef.current = null;
      translatedTextRef.current = null;
      setCanRevert(false);
    }
  }, [setValue]);

  const onInputChange = useCallback((newValue: string) => {
    if (originalTextRef.current !== null && newValue !== translatedTextRef.current) {
      originalTextRef.current = null;
      translatedTextRef.current = null;
      setCanRevert(false);
    }
  }, []);

  const clearTranslateError = useCallback(() => setTranslateError(null), []);

  return { isTranslating, canRevert, translateError, handleTranslate, handleRevert, onInputChange, clearTranslateError };
}
