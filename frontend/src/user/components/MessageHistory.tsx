import { useEffect, useRef } from "react";
import { ActionIcon, Alert, Button, Divider, Group, Stack, Text, Tooltip } from "@mantine/core";
import { IconAlertTriangle, IconFold, IconRefresh, IconTrash } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import { chatStore } from "../stores/ChatStore";
import { MessageBubble } from "./MessageBubble";
import { SummaryBlock } from "./SummaryBlock";

function isSummaryItem(item: ChatSummary | ChatMessage): item is ChatSummary {
  return "start_turn" in item && "end_turn" in item && "start_message_id" in item;
}

export const MessageHistory = observer(function MessageHistory() {
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevLengthRef = useRef(0);
  const items = chatStore.displayItems;
  const isSending = chatStore.isSending;
  const currentTurn = chatStore.currentChat?.session.current_turn ?? 0;

  // Scroll when new messages are added (not on delete/rewind)
  useEffect(() => {
    const prev = prevLengthRef.current;
    prevLengthRef.current = items.length;
    if (items.length > prev) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [items.length]);

  // Scroll during active streaming
  useEffect(() => {
    if (chatStore.isSending) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatStore.streamingContent, chatStore.streamingToolCalls.length]);

  // Scroll on error
  useEffect(() => {
    if (chatStore.error) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatStore.error]);

  function dismissError() {
    chatStore.error = null;
    chatStore.streamingContent = "";
    chatStore.streamingThinking = "";
    chatStore.streamingToolCalls = [];
  }

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
            <MessageBubble
              message={msg}
              {...(msg.role === "assistant" && msg.turn_number === currentTurn && chatStore.hasMultipleVariants
                ? {
                    variants: chatStore.latestTurnVariants,
                    onSelectVariant: (index: number) => chatStore.continueWithVariant(index),
                  }
                : {})}
            />
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

      {/* Fallback: if variants exist but no assistant message at current turn (error/deleted), show last variant */}
      {!isSending && chatStore.hasMultipleVariants && currentTurn > 0
        && !items.some((it) => !("start_turn" in it) && it.role === "assistant" && it.turn_number === currentTurn)
        && (() => {
          const vs = chatStore.latestTurnVariants;
          const last = vs[vs.length - 1];
          if (!last) return null;
          const fallbackMsg: ChatMessage = {
            id: "__variant_fallback__",
            role: "assistant",
            content: last.content,
            turn_number: currentTurn,
            tool_calls: last.tool_calls,
            generation_plan: last.generation_plan ? JSON.stringify(last.generation_plan) : null,
            thinking_content: last.thinking_content,
            is_active_variant: false,
            created_at: last.created_at,
          };
          return (
            <MessageBubble
              message={fallbackMsg}
              variants={vs}
              onSelectVariant={(index: number) => chatStore.continueWithVariant(index)}
            />
          );
        })()}

      {(isSending || chatStore.error) && (chatStore.streamingContent || chatStore.streamingToolCalls.length > 0 || chatStore.streamingThinking) && (
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
          streamingToolCalls={chatStore.streamingToolCalls}
        />
      )}

      {chatStore.error && (
        <Alert
          icon={<IconAlertTriangle size={18} />}
          color="red"
          variant="light"
          title="Generation failed"
          withCloseButton
          onClose={dismissError}
        >
          <Text size="sm" mb="xs">
            {chatStore.debugMode
              ? chatStore.error
              : "Something went wrong during generation. Try again or check server logs."}
          </Text>
          <Group gap="xs">
            <Button
              size="xs"
              variant="light"
              color="blue"
              leftSection={<IconRefresh size={14} />}
              onClick={() => {
                dismissError();
                chatStore.retryAfterError();
              }}
            >
              Retry
            </Button>
            <Button
              size="xs"
              variant="light"
              color="gray"
              leftSection={<IconTrash size={14} />}
              onClick={dismissError}
            >
              Dismiss
            </Button>
          </Group>
        </Alert>
      )}

      <div ref={bottomRef} />
    </Stack>
  );
});
