import { useState } from "react";
import {
  ActionIcon,
  Button,
  Collapse,
  Group,
  Stack,
  Table,
  Text,
  Textarea,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import {
  IconChevronDown,
  IconChevronRight,
  IconCornerUpLeft,
  IconEdit,
  IconRefresh,
  IconTrash,
} from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import ReactMarkdown from "react-markdown";
import { ToolCallTrace } from "./ToolCallTrace";
import { chatStore } from "../stores/ChatStore";

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
  streamingContent?: string;
  streamingThinking?: string;
}

interface GenerationPlanData {
  collected_data: string;
  decisions: string[];
  stat_updates: Array<{ name: string; value: string }>;
}

export const MessageBubble = observer(function MessageBubble({
  message,
  isStreaming,
  streamingContent,
  streamingThinking,
}: MessageBubbleProps) {
  const [thinkOpen, setThinkOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [hovered, setHovered] = useState(false);

  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const content = isStreaming ? streamingContent ?? "" : message.content;
  const debug = chatStore.debugMode;
  const isSummarized = false; // Messages in active list are not summarized
  const currentTurn = chatStore.currentChat?.session.current_turn ?? 0;

  async function handleRewind() {
    if (!confirm(`Rewind to turn ${message.turn_number - 1}?`)) return;
    await chatStore.rewindToTurn(message.turn_number - 1);
  }

  async function handleEdit() {
    setEditValue(message.content);
    setEditing(true);
  }

  async function handleSaveAndResend() {
    const text = editValue.trim();
    if (!text) return;
    setEditing(false);
    await chatStore.editMessage(message.id, text);
  }

  async function handleDelete() {
    if (!confirm("Delete this message?")) return;
    await chatStore.deleteMessage(message.id);
  }

  async function handleRegenerate() {
    if (message.turn_number === currentTurn) {
      await chatStore.regenerate();
    } else {
      await chatStore.regenerateAtTurn(message.turn_number);
    }
  }

  // Parse generation plan JSON
  let plan: GenerationPlanData | null = null;
  if (debug && message.generation_plan) {
    try {
      plan = JSON.parse(message.generation_plan) as GenerationPlanData;
    } catch {
      // ignore parse errors
    }
  }

  if (isSystem) {
    return (
      <Text size="sm" c="dimmed" fs="italic" ta="left" py="xs" component="div">
        <div className="md-body">
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>
      </Text>
    );
  }

  const showActions = !isStreaming && !isSystem && !isSummarized && hovered;

  return (
    <Stack
      gap={4}
      align={isUser ? "flex-end" : "flex-start"}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
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
        {/* Streaming thinking (always shown during streaming) */}
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

        {/* Stored thinking content (debug mode only, loaded messages) */}
        {debug && !isStreaming && message.thinking_content && (
          <>
            <UnstyledButton onClick={() => setThinkOpen((o) => !o)}>
              <Group gap={4}>
                <Text size="xs" c="dimmed">Thinking</Text>
                {thinkOpen ? <IconChevronDown size={12} /> : <IconChevronRight size={12} />}
              </Group>
            </UnstyledButton>
            <Collapse in={thinkOpen}>
              <Text
                size="xs"
                c="dimmed"
                style={{ whiteSpace: "pre-wrap", fontFamily: "monospace", maxHeight: 300, overflow: "auto" }}
              >
                {message.thinking_content}
              </Text>
            </Collapse>
          </>
        )}

        {/* Inline edit mode */}
        {editing ? (
          <Stack gap="xs">
            <Textarea
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              minRows={2}
              maxRows={8}
              autosize
              autoFocus
            />
            <Group gap="xs">
              <Button size="xs" onClick={handleSaveAndResend}>Save & Resend</Button>
              <Button size="xs" variant="subtle" onClick={() => setEditing(false)}>Cancel</Button>
            </Group>
          </Stack>
        ) : (
          <div className="md-body" style={{ fontSize: "var(--mantine-font-size-sm)" }}>
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}

        {/* Tool calls */}
        {!isStreaming && message.tool_calls && message.tool_calls.length > 0 && (
          debug ? (
            <ToolCallTrace toolCalls={message.tool_calls} debugMode />
          ) : null
        )}

        {/* Generation plan (debug mode, chain mode) */}
        {debug && plan && (
          <>
            <UnstyledButton onClick={() => setPlanOpen((o) => !o)}>
              <Group gap={4} mt={4}>
                <Text size="xs" c="dimmed">Generation Plan</Text>
                {planOpen ? <IconChevronDown size={12} /> : <IconChevronRight size={12} />}
              </Group>
            </UnstyledButton>
            <Collapse in={planOpen}>
              <Stack gap="xs" mt="xs" pl="sm" style={{ borderLeft: "2px solid var(--mantine-color-dark-4)" }}>
                {plan.collected_data && (
                  <>
                    <Text size="xs" fw={600} c="dimmed">Collected Data</Text>
                    <Text size="xs" c="dimmed" style={{ whiteSpace: "pre-wrap" }}>
                      {plan.collected_data}
                    </Text>
                  </>
                )}
                {plan.decisions && plan.decisions.length > 0 && (
                  <>
                    <Text size="xs" fw={600} c="dimmed">Decisions</Text>
                    <ul style={{ margin: 0, paddingLeft: 16 }}>
                      {plan.decisions.map((d, i) => (
                        <li key={i}><Text size="xs" c="dimmed">{d}</Text></li>
                      ))}
                    </ul>
                  </>
                )}
                {plan.stat_updates && plan.stat_updates.length > 0 && (
                  <>
                    <Text size="xs" fw={600} c="dimmed">Stat Updates</Text>
                    <Table withTableBorder withColumnBorders>
                      <Table.Tbody>
                        {plan.stat_updates.map((su, i) => (
                          <Table.Tr key={i}>
                            <Table.Td><Text size="xs">{su.name}</Text></Table.Td>
                            <Table.Td><Text size="xs">{su.value}</Text></Table.Td>
                          </Table.Tr>
                        ))}
                      </Table.Tbody>
                    </Table>
                  </>
                )}
              </Stack>
            </Collapse>
          </>
        )}
      </div>

      {/* Action buttons */}
      {showActions && (
        <Group gap={4}>
          {isUser && (
            <>
              <Tooltip label="Edit & resend">
                <ActionIcon variant="subtle" size="xs" color="gray" onClick={handleEdit}>
                  <IconEdit size={12} />
                </ActionIcon>
              </Tooltip>
              <Tooltip label="Delete message">
                <ActionIcon variant="subtle" size="xs" color="gray" onClick={handleDelete}>
                  <IconTrash size={12} />
                </ActionIcon>
              </Tooltip>
            </>
          )}
          {!isUser && (
            <>
              <Tooltip label={`Rewind to turn ${message.turn_number - 1}`}>
                <ActionIcon variant="subtle" size="xs" color="gray" onClick={handleRewind}>
                  <IconCornerUpLeft size={12} />
                </ActionIcon>
              </Tooltip>
              <Tooltip label="Regenerate">
                <ActionIcon variant="subtle" size="xs" color="gray" onClick={handleRegenerate}>
                  <IconRefresh size={12} />
                </ActionIcon>
              </Tooltip>
              <Tooltip label="Delete message">
                <ActionIcon variant="subtle" size="xs" color="gray" onClick={handleDelete}>
                  <IconTrash size={12} />
                </ActionIcon>
              </Tooltip>
            </>
          )}
        </Group>
      )}
    </Stack>
  );
});
