import { ActionIcon, Card, Group, Loader, Stack, Text, Tooltip } from "@mantine/core";
import { IconArrowBackUp, IconChevronDown, IconChevronUp, IconRefresh } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import ReactMarkdown from "react-markdown";
import {
  ChatPageState,
  collapseSummary,
  expandSummary,
  regenerateSummary,
  unsummarizeLast,
} from "../../pages/chatPageState";
import { MessageBubble } from "./MessageBubble";

interface SummaryBlockProps {
  state: ChatPageState;
  summary: ChatSummary;
  isLast?: boolean;
}

export const SummaryBlock = observer(function SummaryBlock({ state, summary, isLast }: SummaryBlockProps) {
  const isExpanded = state.expandedSummaryMessages.has(summary.id);
  const expandedMessages = state.expandedSummaryMessages.get(summary.id);
  const isRegenerating = state.isRegeneratingSummary === summary.id;
  const isBusy = state.isCompacting || state.isSending;

  async function handleExpand() {
    if (isExpanded) {
      collapseSummary(state, summary.id);
    } else {
      await expandSummary(state, summary.id);
    }
  }

  async function handleRegenerate() {
    await regenerateSummary(state, summary.id);
  }

  async function handleUnsummarize() {
    if (!confirm("Undo this summary and restore the original messages?")) return;
    await unsummarizeLast(state, summary.id);
  }

  return (
    <Stack gap={4}>
      <Card
        withBorder
        padding="sm"
        radius="md"
        style={{
          backgroundColor: "var(--mantine-color-dark-7)",
          borderColor: "var(--mantine-color-dark-4)",
          opacity: isRegenerating ? 0.6 : 1,
        }}
      >
        <Group justify="space-between" mb={4}>
          <Text size="xs" fw={600} c="dimmed">
            Summary — Turns {summary.start_turn}–{summary.end_turn}
          </Text>
          <Group gap={4}>
            <Tooltip label={isExpanded ? "Collapse" : "Show original messages"}>
              <ActionIcon
                variant="subtle"
                size="xs"
                color="gray"
                onClick={handleExpand}
                disabled={isRegenerating}
              >
                {isExpanded ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Regenerate summary">
              <ActionIcon
                variant="subtle"
                size="xs"
                color="gray"
                onClick={handleRegenerate}
                disabled={isRegenerating}
              >
                {isRegenerating ? <Loader size={12} /> : <IconRefresh size={14} />}
              </ActionIcon>
            </Tooltip>
            {isLast && (
              <Tooltip label="Undo summary">
                <ActionIcon
                  variant="subtle"
                  size="xs"
                  color="yellow"
                  onClick={handleUnsummarize}
                  disabled={isRegenerating || isBusy}
                >
                  <IconArrowBackUp size={14} />
                </ActionIcon>
              </Tooltip>
            )}
          </Group>
        </Group>

        <div className="md-body" style={{ fontSize: "var(--mantine-font-size-xs)" }}>
          <ReactMarkdown>{summary.content}</ReactMarkdown>
        </div>
      </Card>

      {isExpanded && expandedMessages && (
        <Stack gap={4} pl="md" style={{ opacity: 0.6 }}>
          {expandedMessages.map((msg) => (
            <MessageBubble key={msg.id} state={state} message={msg} />
          ))}
        </Stack>
      )}
    </Stack>
  );
});
