import { useEffect, useRef } from "react";
import { ActionIcon, Alert, Button, Card, Divider, Group, Loader, Stack, Text, Tooltip } from "@mantine/core";
import { IconAlertTriangle, IconFold, IconRefresh, IconTrash } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import ReactMarkdown from "react-markdown";
import {
  ChatPageState,
  compactUpTo,
  continueWithVariant,
  retryAfterError,
} from "../../pages/chatPageState";
import { MessageBubble } from "./MessageBubble";
import { SummaryBlock } from "./SummaryBlock";
import { ToolCallTrace } from "./ToolCallTrace";

function isSummaryItem(item: ChatSummary | ChatMessage): item is ChatSummary {
  return "start_turn" in item && "end_turn" in item && "start_message_id" in item;
}

interface MessageHistoryProps {
  state: ChatPageState;
}

export const MessageHistory = observer(function MessageHistory({ state }: MessageHistoryProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevLengthRef = useRef(0);
  const items = state.displayItems;
  const isSending = state.isSending;
  const currentTurn = state.currentChat?.session.current_turn ?? 0;

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
    if (state.isSending) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [state.streamingContent, state.streamingToolCalls.length]);

  // Scroll during compaction streaming
  useEffect(() => {
    if (state.isCompacting) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [state.compactStreamingContent, state.compactToolCalls.length]);

  // Scroll on error
  useEffect(() => {
    if (state.error) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [state.error]);

  function dismissError() {
    state.error = null;
    state.streamingContent = "";
    state.streamingThinking = "";
    state.streamingToolCalls = [];
  }

  async function handleCompact(messageId: string, turnNumber: number) {
    if (!confirm("Summarize all messages up to this point?")) return;
    const variantIdx = turnNumber === currentTurn ? state.viewingVariantIndex ?? undefined : undefined;
    await compactUpTo(state, messageId, variantIdx);
  }

  let prevTurn = 0;

  return (
    <Stack gap="md" p="md" style={{ flex: 1, overflowY: "auto" }}>
      {items.map((item) => {
        if (isSummaryItem(item)) {
          const lastSummaryId = state.summaries[state.summaries.length - 1]?.id;
          const el = (
            <div key={`summary-${item.id}`}>
              <SummaryBlock state={state} summary={item} isLast={item.id === lastSummaryId} />
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
          msg.turn_number <= currentTurn &&
          !state.isCompacting;

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
              state={state}
              message={msg}
              isSending={isSending}
              currentTurn={currentTurn}
              {...(msg.role === "assistant" && msg.turn_number === currentTurn && state.hasMultipleVariants
                ? {
                    variants: state.latestTurnVariants,
                    onSelectVariant: (index: number) => continueWithVariant(state, index),
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
                  onClick={() => handleCompact(msg.id, msg.turn_number)}
                  loading={state.isCompacting}
                >
                  <IconFold size={12} />
                </ActionIcon>
              </Tooltip>
            )}
          </div>
        );
      })}

      {/* Compact progress indicator */}
      {state.isCompacting && (
        <Card
          withBorder
          padding="sm"
          radius="md"
          style={{
            backgroundColor: "var(--mantine-color-dark-7)",
            borderColor: "var(--mantine-color-dark-4)",
            flexShrink: 0,
          }}
        >
          <Group gap="xs" mb={state.compactStreamingContent ? "xs" : 0}>
            <Loader size={14} />
            <Text size="xs" fw={600} c="dimmed">
              {state.compactPhase === "summarization"
                ? "Writing summary..."
                : state.compactPhase === "memory_extraction"
                  ? "Extracting memories..."
                  : "Starting compaction..."}
            </Text>
          </Group>

          {state.debugMode && state.compactToolCalls.length > 0 && (
            <ToolCallTrace
              toolCalls={state.compactToolCalls.map((tc) => ({
                tool_name: tc.tool_name,
                arguments: tc.arguments as Record<string, string | null>,
                result: tc.result ?? "",
                stage_name: tc.stage_name,
              }))}
              debugMode
              streaming
            />
          )}

          {state.compactStreamingContent && (
            <div className="md-body" style={{ fontSize: "var(--mantine-font-size-xs)" }}>
              <ReactMarkdown>{state.compactStreamingContent}</ReactMarkdown>
            </div>
          )}
        </Card>
      )}

      {/* Fallback: if variants exist but no assistant message at current turn (error/deleted), show last variant */}
      {!isSending && state.hasMultipleVariants && currentTurn > 0
        && !items.some((it) => !("start_turn" in it) && it.role === "assistant" && it.turn_number === currentTurn)
        && (() => {
          const vs = state.latestTurnVariants;
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
            user_instructions: null,
            is_active_variant: false,
            created_at: last.created_at,
          };
          return (
            <MessageBubble
              state={state}
              message={fallbackMsg}
              isSending={isSending}
              currentTurn={currentTurn}
              variants={vs}
              onSelectVariant={(index: number) => continueWithVariant(state, index)}
            />
          );
        })()}

      {(isSending || state.error) && (state.streamingContent || state.streamingToolCalls.length > 0 || state.streamingThinking) && (
        <MessageBubble
          state={state}
          message={{
            id: "__streaming__",
            role: "assistant",
            content: state.streamingContent,
            turn_number: currentTurn + 1,
            tool_calls: null,
            generation_plan: null,
            thinking_content: null,
            user_instructions: null,
            is_active_variant: true,
            created_at: new Date().toISOString(),
          }}
          isStreaming
          isSending={isSending}
          currentTurn={currentTurn}
          streamingContent={state.streamingContent}
          streamingThinking={state.streamingThinking}
          streamingToolCalls={state.streamingToolCalls}
        />
      )}

      {state.error && (
        <Alert
          icon={<IconAlertTriangle size={18} />}
          color="red"
          variant="light"
          title="Generation failed"
          withCloseButton
          onClose={dismissError}
        >
          <Text size="sm" mb="xs">
            {state.debugMode
              ? state.error
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
                retryAfterError(state);
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
