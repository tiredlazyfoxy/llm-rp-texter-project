import { useEffect, useRef } from "react";
import { Divider, Stack, Text } from "@mantine/core";
import { observer } from "mobx-react-lite";
import { chatStore } from "../stores/ChatStore";
import { MessageBubble } from "./MessageBubble";

export const MessageHistory = observer(function MessageHistory() {
  const bottomRef = useRef<HTMLDivElement>(null);
  const messages = chatStore.activeMessages;
  const isSending = chatStore.isSending;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, chatStore.streamingContent]);

  return (
    <Stack gap="md" p="md" style={{ flex: 1, overflowY: "auto" }}>
      {messages.map((msg, i) => {
        const prevMsg = i > 0 ? messages[i - 1] : null;
        const turnChanged = prevMsg && prevMsg.turn_number !== msg.turn_number;
        return (
          <div key={msg.id}>
            {turnChanged && (
              <Divider
                label={<Text size="xs" c="dimmed">Turn {msg.turn_number}</Text>}
                labelPosition="center"
                my="xs"
              />
            )}
            <MessageBubble message={msg} />
          </div>
        );
      })}

      {isSending && chatStore.streamingContent && (
        <MessageBubble
          message={{
            id: "__streaming__",
            role: "assistant",
            content: chatStore.streamingContent,
            turn_number: (chatStore.currentChat?.session.current_turn ?? 0) + 1,
            tool_calls: null,
            is_active_variant: true,
            created_at: new Date().toISOString(),
          }}
          isStreaming
          streamingContent={chatStore.streamingContent}
          streamingThinking={chatStore.streamingThinking}
        />
      )}

      <div ref={bottomRef} />
    </Stack>
  );
});
