import { useEffect, useRef } from "react";
import { ActionIcon, Divider, Stack, Text, Tooltip } from "@mantine/core";
import { IconFold } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import { chatStore } from "../stores/ChatStore";
import { MessageBubble } from "./MessageBubble";
import { SummaryBlock } from "./SummaryBlock";

function isSummaryItem(item: ChatSummary | ChatMessage): item is ChatSummary {
  return "start_turn" in item && "end_turn" in item && "start_message_id" in item;
}

export const MessageHistory = observer(function MessageHistory() {
  const bottomRef = useRef<HTMLDivElement>(null);
  const items = chatStore.displayItems;
  const isSending = chatStore.isSending;
  const currentTurn = chatStore.currentChat?.session.current_turn ?? 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [items.length, chatStore.streamingContent]);

  async function handleCompact(messageId: string) {
    if (!confirm("Summarize all messages up to this point?")) return;
    await chatStore.compactUpTo(messageId);
  }

  let prevTurn = 0;

  return (
    <Stack gap="md" p="md" style={{ flex: 1, overflowY: "auto" }}>
      {items.map((item) => {
        if (isSummaryItem(item)) {
          const el = (
            <div key={`summary-${item.id}`}>
              <SummaryBlock summary={item} />
            </div>
          );
          prevTurn = item.end_turn;
          return el;
        }

        const msg = item;
        const turnChanged = prevTurn !== 0 && prevTurn !== msg.turn_number;
        prevTurn = msg.turn_number;

        const showCompact =
          msg.role === "assistant" &&
          msg.turn_number < currentTurn &&
          !chatStore.isCompacting;

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
            {showCompact && (
              <Tooltip label="Summarize messages up to here" position="right">
                <ActionIcon
                  variant="subtle"
                  size="xs"
                  color="gray"
                  mt={2}
                  onClick={() => handleCompact(msg.id)}
                  loading={chatStore.isCompacting}
                >
                  <IconFold size={12} />
                </ActionIcon>
              </Tooltip>
            )}
          </div>
        );
      })}

      {isSending && chatStore.streamingContent && (
        <MessageBubble
          message={{
            id: "__streaming__",
            role: "assistant",
            content: chatStore.streamingContent,
            turn_number: currentTurn + 1,
            tool_calls: null,
            generation_plan: null,
            thinking_content: null,
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
