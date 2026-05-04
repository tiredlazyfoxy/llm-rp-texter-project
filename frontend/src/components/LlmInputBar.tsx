import { useState, type ReactNode } from "react";
import { ActionIcon, Group, Text, Textarea, Tooltip, type TextareaProps } from "@mantine/core";
import { IconArrowBackUp, IconLanguage, IconPlayerStop, IconSend } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import type { TranslateStreamFn } from "../types/llmChat";
import {
  LlmInputState,
  clearTranslateError,
  onValueEdit,
  revertTranslate,
  startTranslate,
} from "./llmInputState";

interface LlmInputBarProps {
  value: string;
  onChange: (v: string) => void;
  /** Optional: omit to hide translate UI. */
  translateFn?: TranslateStreamFn;
  /** External busy → disables input, shows stop button. */
  busy?: boolean;
  onSend: () => void;
  /** When `busy`, wired to the stop button. */
  onStop?: () => void;
  /** Hard-disable (e.g., chat archived). */
  disabled?: boolean;
  placeholder?: string;
  /** Slot above the textarea row (e.g., OOC preview, status row). */
  before?: ReactNode;
  /** Slot after the send/stop button (e.g., regenerate). */
  extras?: ReactNode;
  /** Default true; Shift+Enter = newline. */
  submitOnEnter?: boolean;
  /** Pass-through Mantine textarea styling/sizing props. */
  textareaProps?: Omit<TextareaProps, "value" | "onChange" | "onKeyDown" | "disabled" | "placeholder">;
}

export const LlmInputBar = observer(function LlmInputBar({
  value,
  onChange,
  translateFn,
  busy = false,
  onSend,
  onStop,
  disabled = false,
  placeholder,
  before,
  extras,
  submitOnEnter = true,
  textareaProps,
}: LlmInputBarProps) {
  const [tx] = useState(() => new LlmInputState());

  const inputDisabled = disabled || busy || tx.isTranslating;
  const sendDisabled = disabled || !value.trim();
  const showStop = busy;
  const stopDisabled = !onStop;

  function handleChange(newValue: string) {
    onChange(newValue);
    onValueEdit(tx, newValue);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (submitOnEnter && e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!sendDisabled && !busy) onSend();
    }
  }

  return (
    <>
      {before}
      {tx.translateError && (
        <Text
          size="xs"
          c="red"
          mb={4}
          onClick={() => clearTranslateError(tx)}
          style={{ cursor: "pointer" }}
        >
          {tx.translateError}
        </Text>
      )}
      <Group align="flex-end" gap="xs" style={{ flex: 1, overflow: "hidden" }}>
        <Textarea
          {...textareaProps}
          value={value}
          onChange={(e) => handleChange(e.currentTarget.value)}
          onKeyDown={handleKeyDown}
          disabled={inputDisabled}
          placeholder={placeholder}
        />

        {translateFn && (
          <Tooltip label="Translate to English">
            <ActionIcon
              variant="subtle"
              size="lg"
              onClick={() => startTranslate(tx, translateFn, value, onChange)}
              disabled={!value.trim() || disabled || busy || tx.isTranslating}
              loading={tx.isTranslating}
            >
              <IconLanguage size={18} />
            </ActionIcon>
          </Tooltip>
        )}

        {tx.canRevert && (
          <Tooltip label="Revert to original">
            <ActionIcon
              variant="subtle"
              size="lg"
              color="orange"
              onClick={() => revertTranslate(tx, onChange)}
            >
              <IconArrowBackUp size={18} />
            </ActionIcon>
          </Tooltip>
        )}

        {showStop ? (
          <Tooltip label="Stop generation">
            <ActionIcon
              color="red"
              variant="filled"
              size="lg"
              onClick={() => onStop?.()}
              disabled={stopDisabled}
            >
              <IconPlayerStop size={18} />
            </ActionIcon>
          </Tooltip>
        ) : (
          <Tooltip label="Send">
            <ActionIcon
              color="blue"
              variant="filled"
              size="lg"
              disabled={sendDisabled}
              onClick={onSend}
            >
              <IconSend size={18} />
            </ActionIcon>
          </Tooltip>
        )}

        {extras}
      </Group>
    </>
  );
});
