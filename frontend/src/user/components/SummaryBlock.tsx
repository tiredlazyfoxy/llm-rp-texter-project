import { ActionIcon, Card, Group, Loader, Stack, Text, Tooltip } from "@mantine/core";
import { IconChevronDown, IconChevronUp, IconRefresh } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import ReactMarkdown from "react-markdown";
import { chatStore } from "../stores/ChatStore";
import { MessageBubble } from "./MessageBubble";

interface SummaryBlockProps {
  summary: ChatSummary;
}

export const SummaryBlock = observer(function SummaryBlock({ summary }: SummaryBlockProps) {
  const isExpanded = chatStore.expandedSummaryMessages.has(summary.id);
  const expandedMessages = chatStore.expandedSummaryMessages.get(summary.id);
  const isRegenerating = chatStore.isRegeneratingSummary === summary.id;

  async function handleExpand() {
    if (isExpanded) {
      chatStore.collapseSummary(summary.id);
    } else {
      await chatStore.expandSummary(summary.id);
    }
  }

  async function handleRegenerate() {
    await chatStore.regenerateSummary(summary.id);
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
          </Group>
        </Group>

        <div className="md-body" style={{ fontSize: "var(--mantine-font-size-xs)" }}>
          <ReactMarkdown>{summary.content}</ReactMarkdown>
        </div>
      </Card>

      {isExpanded && expandedMessages && (
        <Stack gap={4} pl="md" style={{ opacity: 0.6 }}>
          {expandedMessages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
        </Stack>
      )}
    </Stack>
  );
});
