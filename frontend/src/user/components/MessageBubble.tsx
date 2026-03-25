import { useEffect, useState } from "react";
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
  IconCheck,
  IconChevronDown,
  IconChevronLeft,
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

interface StreamingToolCall {
  tool_name: string;
  arguments: Record<string, string>;
  result?: string;
}

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
  streamingContent?: string;
  streamingThinking?: string;
  streamingToolCalls?: StreamingToolCall[];
  variants?: GenerationVariant[];
  onSelectVariant?: (index: number) => void;
}

function ThinkingSection({ label, content }: { label: string; content: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <UnstyledButton onClick={() => setOpen((o) => !o)}>
        <Group gap={4}>
          {open ? <IconChevronDown size={12} /> : <IconChevronRight size={12} />}
          <Text size="xs" c="dimmed" fw={600}>{label} — Thinking</Text>
        </Group>
      </UnstyledButton>
      <Collapse in={open}>
        <Text
          size="xs"
          c="dimmed"
          style={{ whiteSpace: "pre-wrap", fontFamily: "monospace", maxHeight: 300, overflow: "auto" }}
          mt={2}
          pl="xs"
        >
          {content}
        </Text>
      </Collapse>
    </div>
  );
}

export const MessageBubble = observer(function MessageBubble({
  message,
  isStreaming,
  streamingContent,
  streamingThinking,
  streamingToolCalls,
  variants,
  onSelectVariant,
}: MessageBubbleProps) {
  const [thinkOpen, setThinkOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [variantIndex, setVariantIndex] = useState(-1); // -1 = current message (latest)

  // variants = old generations stored on session; current message is the latest
  // Total count: variants.length + 1 (current). Index 0..N-1 = variants, N = current message.
  const hasVariants = variants && variants.length > 0;
  const totalCount = hasVariants ? variants.length + 1 : 1;
  const displayIndex = variantIndex < 0 ? totalCount - 1 : variantIndex;
  const isViewingVariant = hasVariants && displayIndex < variants.length;
  const viewedVariant = isViewingVariant ? variants[displayIndex] : null;

  // Reset to latest when variants array grows (after regenerate)
  useEffect(() => {
    if (hasVariants) setVariantIndex(-1);
  }, [variants?.length]);

  // Track which variant the user is viewing for auto-commit on send
  useEffect(() => {
    chatStore.viewingVariantIndex = isViewingVariant ? displayIndex : null;
  }, [isViewingVariant, displayIndex]);

  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const content = isStreaming
    ? streamingContent ?? ""
    : viewedVariant ? viewedVariant.content : message.content;
  const debug = chatStore.debugMode;
  const isSummarized = false; // Messages in active list are not summarized
  const currentTurn = chatStore.currentChat?.session.current_turn ?? 0;

  // Resolve display fields: variant (rich types) or message (JSON strings)
  const displayToolCalls = viewedVariant ? viewedVariant.tool_calls : message.tool_calls;
  const displayThinking = viewedVariant ? viewedVariant.thinking_content : message.thinking_content;

  // Parse structured thinking (per-stage) or fall back to flat text
  let thinkingParts: ThinkingPart[] | null = null;
  if (debug && displayThinking) {
    try {
      const parsed: unknown = JSON.parse(displayThinking);
      if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0].stage_name === "string") {
        thinkingParts = parsed as ThinkingPart[];
      }
    } catch {
      // plain text (old format) — thinkingParts stays null
    }
  }

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

  // Parse generation plan: variant has rich object, message has JSON string
  let plan: GenerationPlanData | null = null;
  if (debug) {
    if (viewedVariant) {
      plan = viewedVariant.generation_plan ?? null;
    } else if (message.generation_plan) {
      try {
        plan = JSON.parse(message.generation_plan) as GenerationPlanData;
      } catch {
        // ignore parse errors
      }
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

  const showActions = !isStreaming && !isSystem && !isSummarized;
  const actionsDisabled = chatStore.isSending;

  return (
    <Stack
      gap={4}
      align={isUser ? "flex-end" : "flex-start"}
    >
      <div
        style={{
          maxWidth: "75%",
          width: editing ? "75%" : undefined,
          padding: "10px 14px",
          borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
          backgroundColor: isUser
            ? "var(--mantine-color-steel-7)"
            : "var(--mantine-color-dark-5)",
        }}
      >
        {/* Variant switcher */}
        {hasVariants && !isStreaming && (
          <Group gap={4} mb={4} justify="space-between">
            <Group gap={4}>
              <ActionIcon
                variant="subtle"
                size="xs"
                color="gray"
                disabled={displayIndex === 0}
                onClick={() => setVariantIndex(displayIndex - 1)}
              >
                <IconChevronLeft size={12} />
              </ActionIcon>
              <Text size="xs" c="dimmed">
                {displayIndex + 1} / {totalCount}
              </Text>
              <ActionIcon
                variant="subtle"
                size="xs"
                color="gray"
                disabled={displayIndex === totalCount - 1}
                onClick={() => setVariantIndex(displayIndex + 1)}
              >
                <IconChevronRight size={12} />
              </ActionIcon>
            </Group>
            {isViewingVariant && onSelectVariant && (
              <Tooltip label="Use this variant">
                <ActionIcon
                  variant="light"
                  size="xs"
                  color="green"
                  disabled={actionsDisabled}
                  onClick={() => onSelectVariant(displayIndex)}
                >
                  <IconCheck size={12} />
                </ActionIcon>
              </Tooltip>
            )}
          </Group>
        )}

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

        {/* Streaming tool calls */}
        {isStreaming && streamingToolCalls && streamingToolCalls.length > 0 && (
          <ToolCallTrace toolCalls={streamingToolCalls as ToolCallInfo[]} debugMode={debug} streaming />
        )}

        {/* Stored thinking content (debug mode only, loaded messages) */}
        {debug && !isStreaming && displayThinking && (
          thinkingParts ? (
            // Per-stage structured thinking
            <Stack gap={4} mt={4}>
              {thinkingParts.map((tp, i) => (
                <ThinkingSection key={i} label={tp.stage_name} content={tp.content} />
              ))}
            </Stack>
          ) : (
            // Legacy flat thinking text
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
                  {displayThinking}
                </Text>
              </Collapse>
            </>
          )
        )}

        {/* Tool calls (above content for completed messages) */}
        {!isStreaming && displayToolCalls && displayToolCalls.length > 0 && (
          <ToolCallTrace toolCalls={displayToolCalls} debugMode={debug} defaultCollapsed />
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
              styles={{
                input: {
                  fontSize: "var(--mantine-font-size-sm)",
                  backgroundColor: "transparent",
                  border: "1px solid var(--mantine-color-dark-3)",
                  color: "inherit",
                },
              }}
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

        {/* Action buttons */}
        {showActions && (
          <Group gap={4} mt={4}>
            {isUser && (
              <>
                <Tooltip label="Edit & resend">
                  <ActionIcon variant="subtle" size="xs" color="gray" disabled={actionsDisabled} onClick={handleEdit}>
                    <IconEdit size={12} />
                  </ActionIcon>
                </Tooltip>
                <Tooltip label="Delete message">
                  <ActionIcon variant="subtle" size="xs" color="gray" disabled={actionsDisabled} onClick={handleDelete}>
                    <IconTrash size={12} />
                  </ActionIcon>
                </Tooltip>
              </>
            )}
            {!isUser && (
              <>
                <Tooltip label={`Rewind to turn ${message.turn_number - 1}`}>
                  <ActionIcon variant="subtle" size="xs" color="gray" disabled={actionsDisabled} onClick={handleRewind}>
                    <IconCornerUpLeft size={12} />
                  </ActionIcon>
                </Tooltip>
                <Tooltip label="Regenerate">
                  <ActionIcon variant="subtle" size="xs" color="gray" disabled={actionsDisabled} onClick={handleRegenerate}>
                    <IconRefresh size={12} />
                  </ActionIcon>
                </Tooltip>
                <Tooltip label="Delete message">
                  <ActionIcon variant="subtle" size="xs" color="gray" disabled={actionsDisabled} onClick={handleDelete}>
                    <IconTrash size={12} />
                  </ActionIcon>
                </Tooltip>
              </>
            )}
          </Group>
        )}
      </div>
    </Stack>
  );
});
