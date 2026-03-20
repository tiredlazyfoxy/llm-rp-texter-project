import { useRef, useState } from "react";
import { ActionIcon, Group, Textarea, Tooltip } from "@mantine/core";
import { IconPlayerStop, IconRefresh, IconSend } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import { chatStore } from "../stores/ChatStore";

export const ChatInput = observer(function ChatInput() {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const disabled = chatStore.currentChat?.session.status !== "active";

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
      <Group align="flex-end" gap="xs">
        <Textarea
          ref={textareaRef}
          style={{ flex: 1 }}
          placeholder={disabled ? "Chat archived" : "Type your message… (Enter to send, Shift+Enter for newline)"}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          minRows={1}
          maxRows={6}
          autosize
          disabled={disabled || chatStore.isSending}
        />

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
