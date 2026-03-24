import { useCallback, useRef, useState } from "react";
import { ActionIcon, Badge, Group, Loader, Text, Textarea, Tooltip } from "@mantine/core";
import { IconArrowBackUp, IconLanguage, IconPlayerStop, IconRefresh, IconSend } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import { translateTextChat } from "../../api/chat";
import { useTranslation } from "../../hooks/useTranslation";
import { chatStore } from "../stores/ChatStore";

export const ChatInput = observer(function ChatInput() {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const disabled = chatStore.currentChat?.session.status !== "active";

  const getValue = useCallback(() => value, [value]);
  const { isTranslating, canRevert, translateError, handleTranslate, handleRevert, onInputChange, clearTranslateError } = useTranslation({
    getValue,
    setValue,
    translateFn: translateTextChat,
  });

  async function handleSend() {
    const text = value.trim();
    if (!text || chatStore.isSending) return;
    setValue("");
    await chatStore.sendMessage(text);
  }

  async function handleRegenerate() {
    if (chatStore.isSending) return;
    await chatStore.regenerate();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div style={{ padding: "8px 12px", borderTop: "1px solid var(--mantine-color-dark-4)" }}>
      {translateError && (
        <Text size="xs" c="red" mb={4} onClick={clearTranslateError} style={{ cursor: "pointer" }}>
          {translateError}
        </Text>
      )}
      {chatStore.isSending && chatStore.currentStatus && (
        <Group gap="xs" mb={4} align="center">
          <Loader size={12} />
          {chatStore.currentPhase && (
            <Badge size="xs" variant="light" color={chatStore.currentPhase === "planning" ? "violet" : "teal"}>
              {chatStore.currentPhase === "planning" ? "Planning" : "Writing"}
            </Badge>
          )}
          <Text size="xs" c="dimmed">{chatStore.currentStatus}</Text>
        </Group>
      )}
      <Group align="flex-end" gap="xs">
        <Textarea
          ref={textareaRef}
          style={{ flex: 1 }}
          placeholder={disabled ? "Chat archived" : "Type your message… (Enter to send, Shift+Enter for newline)"}
          value={value}
          onChange={(e) => { setValue(e.target.value); onInputChange(e.target.value); }}
          onKeyDown={handleKeyDown}
          minRows={1}
          maxRows={6}
          autosize
          disabled={disabled || chatStore.isSending}
        />

        <Tooltip label="Translate to English">
          <ActionIcon
            variant="subtle"
            size="lg"
            onClick={handleTranslate}
            disabled={!value.trim() || disabled || chatStore.isSending || isTranslating}
            loading={isTranslating}
          >
            <IconLanguage size={18} />
          </ActionIcon>
        </Tooltip>

        {canRevert && (
          <Tooltip label="Revert to original">
            <ActionIcon variant="subtle" size="lg" color="orange" onClick={handleRevert}>
              <IconArrowBackUp size={18} />
            </ActionIcon>
          </Tooltip>
        )}

        {chatStore.isSending ? (
          <Tooltip label="Stop generation">
            <ActionIcon
              color="red"
              variant="filled"
              size="lg"
              onClick={() => chatStore.stopGeneration()}
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
              disabled={!value.trim() || disabled}
              onClick={handleSend}
            >
              <IconSend size={18} />
            </ActionIcon>
          </Tooltip>
        )}

        {!chatStore.isSending && chatStore.activeMessages.some((m) => m.role === "assistant") && (
          <Tooltip label="Regenerate">
            <ActionIcon variant="subtle" size="lg" onClick={handleRegenerate} disabled={disabled}>
              <IconRefresh size={18} />
            </ActionIcon>
          </Tooltip>
        )}
      </Group>
    </div>
  );
});
