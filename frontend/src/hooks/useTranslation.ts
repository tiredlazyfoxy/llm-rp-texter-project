import { useCallback, useRef, useState } from "react";
import type { TranslateRequest, TranslateResponse } from "../types/llmChat";

interface UseTranslationOptions {
  getValue: () => string;
  setValue: (text: string) => void;
  getModelId: () => string | null;
  translateFn: (req: TranslateRequest) => Promise<TranslateResponse>;
}

interface UseTranslationReturn {
  isTranslating: boolean;
  canRevert: boolean;
  handleTranslate: () => Promise<void>;
  handleRevert: () => void;
  onInputChange: (newValue: string) => void;
}

export function useTranslation({
  getValue,
  setValue,
  getModelId,
  translateFn,
}: UseTranslationOptions): UseTranslationReturn {
  const [isTranslating, setIsTranslating] = useState(false);
  const [canRevert, setCanRevert] = useState(false);
  const originalTextRef = useRef<string | null>(null);
  const translatedTextRef = useRef<string | null>(null);

  const handleTranslate = useCallback(async () => {
    const text = getValue().trim();
    const modelId = getModelId();
    if (!text || !modelId) return;

    setIsTranslating(true);
    try {
      const res = await translateFn({ text, model_id: modelId });
      originalTextRef.current = getValue();
      translatedTextRef.current = res.translated_text;
      setValue(res.translated_text);
      setCanRevert(true);
    } catch {
      // Leave input unchanged on error
    } finally {
      setIsTranslating(false);
    }
  }, [getValue, setValue, getModelId, translateFn]);

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

  return { isTranslating, canRevert, handleTranslate, handleRevert, onInputChange };
}
