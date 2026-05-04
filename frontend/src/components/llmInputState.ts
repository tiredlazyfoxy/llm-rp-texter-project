import { makeAutoObservable } from "mobx";
import type { TranslateStreamFn } from "../types/llmChat";
import { getTranslationSettings } from "../utils/translationSettings";

/**
 * Internal state for `LlmInputBar`. One instance per component mount,
 * created via `useState(() => new LlmInputState())`.
 *
 * Mutations live as external `(state, ...args)` functions below to keep
 * the class as pure data — matching the project-wide MobX rule.
 */
export class LlmInputState {
  isTranslating = false;
  canRevert = false;
  translateError: string | null = null;

  // Internal buffers — observable so component re-renders pick them up
  // mid-stream is fine, but they're read-only outside this module.
  originalText: string | null = null;
  translatedText: string | null = null;
  thinkingBuffer = "";
  tokenBuffer = "";
  gotToken = false;

  // Non-observable: AbortController for an in-flight translate.
  abortCtrl: AbortController | null = null;

  constructor() {
    makeAutoObservable(this, { abortCtrl: false });
  }
}

/**
 * Start a streaming translate: aborts any prior translate, fails fast if
 * no model is configured, streams thinking → tokens → done into the
 * textarea via `setValue`. On error, restores the original text.
 */
export function startTranslate(
  state: LlmInputState,
  translateFn: TranslateStreamFn,
  value: string,
  setValue: (v: string) => void,
): void {
  const text = value.trim();
  if (!text) return;

  const settings = getTranslationSettings();
  if (!settings.translate_model_id) {
    state.translateError =
      "No translation model configured. Set it in Translation Settings (user menu).";
    return;
  }
  state.translateError = null;

  // Abort any prior in-flight translate
  if (state.abortCtrl) {
    state.abortCtrl.abort();
    state.abortCtrl = null;
  }

  state.originalText = value;
  state.thinkingBuffer = "";
  state.tokenBuffer = "";
  state.gotToken = false;
  state.isTranslating = true;

  state.abortCtrl = translateFn(
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
        state.thinkingBuffer += content;
        setValue(state.thinkingBuffer);
      },
      onToken: (content) => {
        if (!state.gotToken) state.gotToken = true;
        state.tokenBuffer += content;
        setValue(state.tokenBuffer);
      },
      onDone: (content) => {
        state.translatedText = content;
        setValue(content);
        state.isTranslating = false;
        state.canRevert = true;
        state.abortCtrl = null;
      },
      onError: (message) => {
        if (state.originalText !== null) {
          setValue(state.originalText);
        }
        state.originalText = null;
        state.translatedText = null;
        state.isTranslating = false;
        state.translateError = message;
        state.abortCtrl = null;
      },
    },
  );
}

/** Restore the pre-translate text and clear revert state. */
export function revertTranslate(
  state: LlmInputState,
  setValue: (v: string) => void,
): void {
  if (state.originalText !== null) {
    setValue(state.originalText);
    state.originalText = null;
    state.translatedText = null;
    state.canRevert = false;
  }
}

/** Abort an in-flight translate. */
export function stopTranslate(state: LlmInputState): void {
  if (state.abortCtrl) {
    state.abortCtrl.abort();
    state.abortCtrl = null;
  }
  state.isTranslating = false;
}

/** Clear the translate-error banner. */
export function clearTranslateError(state: LlmInputState): void {
  state.translateError = null;
}

/**
 * Call after every textarea change. If the user manually edits while in
 * a revertable state, drop the revert buffer.
 */
export function onValueEdit(state: LlmInputState, newValue: string): void {
  if (state.originalText !== null && newValue !== state.translatedText) {
    state.originalText = null;
    state.translatedText = null;
    state.canRevert = false;
  }
}
