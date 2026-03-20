import { useState } from "react";
import { ActionIcon, Collapse, Group, Stack, Text, Tooltip, UnstyledButton } from "@mantine/core";
import { IconChevronDown, IconChevronRight, IconCornerUpLeft } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import { ToolCallTrace } from "./ToolCallTrace";
import { chatStore } from "../stores/ChatStore";

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
  streamingContent?: string;
  streamingThinking?: string;
}

export const MessageBubble = observer(function MessageBubble({
  message,
  isStreaming,
  streamingContent,
  streamingThinking,
}: MessageBubbleProps) {
  const [thinkOpen, setThinkOpen] = useState(false);
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const content = isStreaming ? streamingContent ?? "" : message.content;

  async function handleRewind() {
    if (!confirm(`Rewind to turn ${message.turn_number - 1}?`)) return;
    await chatStore.rewindToTurn(message.turn_number - 1);
  }

  if (isSystem) {
    return (
      <Text size="sm" c="dimmed" fs="italic" ta="center" py="xs">
        {content}
      </Text>
    );
  }

  return (
    <Stack gap={4} align={isUser ? "flex-end" : "flex-start"}>
      <div
        style={{
          maxWidth: "75%",
          padding: "10px 14px",
          borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
          backgroundColor: isUser
            ? "var(--mantine-color-steel-7)"
            : "var(--mantine-color-dark-5)",
        }}
      >
        {streamingThinking && (
          <>
            <UnstyledButton onClick={() => setThinkOpen((o) => !o)}>
              <Group gap={4}>
                <Text size="xs" c="dimmed">Thinking</Text>
                {thinkOpen ? <IconChevronDown size={12} /> : <IconChevronRight size={12} />}
              </Group>
            </UnstyledButton>
            <Collapse in={thinkOpen}>
              <Text size="xs" c="dimmed" fs="italic" style={{ whiteSpace: "pre-wrap" }}>
                {streamingThinking}
              </Text>
            </Collapse>
          </>
        )}

        <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>{content}</Text>

        {!isStreaming && message.tool_calls && message.tool_calls.length > 0 && (
          <ToolCallTrace toolCalls={message.tool_calls} />
        )}
      </div>

      {!isUser && !isStreaming && (
        <Tooltip label={`Rewind to turn ${message.turn_number - 1}`} position="right">
          <ActionIcon variant="subtle" size="xs" color="gray" onClick={handleRewind}>
            <IconCornerUpLeft size={12} />
          </ActionIcon>
        </Tooltip>
      )}
    </Stack>
  );
});
