import { useEffect, useRef, useState } from "react";
import { observer } from "mobx-react-lite";
import { autorun } from "mobx";
import {
  ActionIcon,
  Button,
  Collapse,
  Group,
  Paper,
  ScrollArea,
  Select,
  Slider,
  Stack,
  Switch,
  Text,
  Title,
} from "@mantine/core";
import {
  IconCheck,
  IconChevronDown,
  IconChevronRight,
  IconPlus,
  IconRefresh,
  IconSettings,
  IconTrash,
} from "@tabler/icons-react";
import type { ChatMessage, ToolCallEntry } from "../../../types/llmChat";
import { translateTextAdmin } from "../../../api/llmChat";
import { LlmInputBar } from "../../../components/LlmInputBar";
import {
  LlmChatPanelState,
  type LlmChatRequestContext,
  clearMessages,
  deleteMessage,
  loadModels,
  regenerateAtMessage,
  regenerateLast,
  sendChatMessage,
  setParam,
  setParamsOpen,
  setSelectedModel,
  stopChat,
} from "./llmChatPanelState";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface LlmChatPanelProps {
  currentContent: string;
  worldId?: string;
  // Document mode
  docId?: string;
  docType?: "location" | "npc" | "lore_fact";
  // World field mode
  fieldType?: "description" | "system_prompt" | "initial_message" | "pipeline_prompt";
  onApply: (content: string) => void;
  onAppend: (content: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const LlmChatPanel = observer(function LlmChatPanel({
  currentContent,
  worldId,
  docId,
  docType,
  fieldType,
  onApply,
  onAppend,
}: LlmChatPanelProps) {
  const [state] = useState(() => new LlmChatPanelState());
  const [input, setInput] = useState("");

  // Refs for the auto-scroll behavior. Both are component-local UI plumbing.
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const isAtBottom = useRef(true);

  // Always read the freshest request context from props inside callbacks.
  const ctxRef = useRef<LlmChatRequestContext>({
    currentContent,
    worldId,
    docId,
    docType,
    fieldType,
  });
  ctxRef.current = { currentContent, worldId, docId, docType, fieldType };

  // ---- Mount: load models, attach scroll listener, autorun for auto-scroll
  useEffect(() => {
    const ctrl = new AbortController();
    void loadModels(state, ctrl.signal);

    const el = scrollRef.current;
    const handleScroll = () => {
      if (!el) return;
      isAtBottom.current = el.scrollTop + el.clientHeight >= el.scrollHeight - 40;
    };
    el?.addEventListener("scroll", handleScroll);

    // React to message-list changes — scroll to bottom only when the
    // user is already pinned there. Tracks `state.messages.length` and
    // the streaming content of the last assistant message.
    const dispose = autorun(() => {
      // Touch fields the autorun should react to.
      void state.messages.length;
      const last = state.messages[state.messages.length - 1];
      if (last) {
        void last.content.length;
        void (last.thinkingContent?.length ?? 0);
        void (last.toolCalls?.length ?? 0);
      }
      if (isAtBottom.current && scrollRef.current) {
        const node = scrollRef.current;
        node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
      }
    });

    return () => {
      ctrl.abort();
      el?.removeEventListener("scroll", handleScroll);
      dispose();
      // If a stream is mid-flight when the panel unmounts, abort it.
      if (state.isStreaming) stopChat(state);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- Handlers ------------------------------------------------------------

  const handleSend = () => {
    if (!state.selectedModel || state.isStreaming || !input.trim()) return;
    isAtBottom.current = true;
    sendChatMessage(state, input, ctxRef.current);
    setInput("");
  };

  const handleStop = () => stopChat(state);
  const handleRegenerate = () => regenerateLast(state, ctxRef.current);
  const handleRegenerateMsg = (id: string) => regenerateAtMessage(state, id, ctxRef.current);
  const handleDelete = (id: string) => deleteMessage(state, id);
  const handleClear = () => clearMessages(state);

  // ---- Render --------------------------------------------------------------

  return (
    <Paper p="md" mb="md" withBorder>
      <Stack gap="sm">
        <Group justify="space-between">
          <Title order={5}>LLM Chat</Title>
          <Group gap="xs">
            <Button
              variant="subtle"
              size="xs"
              leftSection={<IconSettings size={14} />}
              onClick={() => setParamsOpen(state, !state.paramsOpen)}
            >
              Params
            </Button>
            <Button
              variant="subtle"
              size="xs"
              color="red"
              leftSection={<IconTrash size={14} />}
              onClick={handleClear}
            >
              Clear
            </Button>
          </Group>
        </Group>

        {/* Model selector */}
        <Select
          placeholder="Select model"
          data={state.modelOptions}
          value={state.selectedModel}
          onChange={(v) => setSelectedModel(state, v)}
          searchable
          size="sm"
        />

        {/* Parameters */}
        <Collapse in={state.paramsOpen}>
          <Paper p="sm" withBorder>
            <Stack gap="xs">
              <Text size="xs" fw={600}>Temperature ({state.params.temperature})</Text>
              <Slider
                min={0} max={2} step={0.1}
                value={state.params.temperature}
                onChange={(v) => setParam(state, "temperature", v)}
              />
              <Text size="xs" fw={600}>Top-p ({state.params.top_p})</Text>
              <Slider
                min={0} max={1} step={0.05}
                value={state.params.top_p}
                onChange={(v) => setParam(state, "top_p", v)}
              />
              <Text size="xs" fw={600}>
                Repetition penalty ({state.params.repetition_penalty})
              </Text>
              <Slider
                min={1} max={2} step={0.05}
                value={state.params.repetition_penalty}
                onChange={(v) => setParam(state, "repetition_penalty", v)}
              />
              <Switch
                label="Thinking mode"
                checked={state.params.enable_thinking}
                onChange={(e) => setParam(state, "enable_thinking", e.currentTarget.checked)}
              />
              <Switch
                label="Use tools (search, lore, web)"
                checked={state.params.enable_tools}
                onChange={(e) => setParam(state, "enable_tools", e.currentTarget.checked)}
              />
            </Stack>
          </Paper>
        </Collapse>

        {/* Messages */}
        <ScrollArea
          h={350}
          viewportRef={scrollRef}
          type="auto"
          styles={{ viewport: { padding: 4 } }}
        >
          <Stack gap="sm">
            {state.messages.length === 0 && (
              <Text c="dimmed" ta="center" size="sm" py="xl">
                Send a message to start chatting with the LLM.
              </Text>
            )}
            {state.messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                msg={msg}
                onApply={onApply}
                onAppend={onAppend}
                onDelete={handleDelete}
                onRegenerate={handleRegenerateMsg}
              />
            ))}
          </Stack>
        </ScrollArea>

        {/* Input area */}
        <LlmInputBar
          value={input}
          onChange={setInput}
          translateFn={translateTextAdmin}
          busy={state.isStreaming}
          onSend={handleSend}
          onStop={handleStop}
          disabled={!state.selectedModel}
          placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
          textareaProps={{
            autosize: true,
            minRows: 1,
            maxRows: 5,
            style: { flex: 1 },
          }}
        />

        {/* Regenerate — only when last message is a completed assistant message */}
        {state.messages.length > 0 &&
          state.messages[state.messages.length - 1].role === "assistant" &&
          !state.messages[state.messages.length - 1].isStreaming && (
            <Group justify="center">
              <Button
                variant="subtle"
                size="xs"
                leftSection={<IconRefresh size={14} />}
                onClick={handleRegenerate}
              >
                Regenerate
              </Button>
            </Group>
          )}
      </Stack>
    </Paper>
  );
});

// ---------------------------------------------------------------------------
// MessageBubble sub-component
// ---------------------------------------------------------------------------

interface MessageBubbleProps {
  msg: ChatMessage;
  onApply: (content: string) => void;
  onAppend: (content: string) => void;
  onDelete: (id: string) => void;
  onRegenerate: (id: string) => void;
}

const MessageBubble = observer(function MessageBubble({
  msg,
  onApply,
  onAppend,
  onDelete,
  onRegenerate,
}: MessageBubbleProps) {
  const [thinkingOpen, setThinkingOpen] = useState(false);
  const isUser = msg.role === "user";

  return (
    <Paper
      p="xs"
      withBorder
      bg={isUser ? "dark.5" : "dark.6"}
      style={{ alignSelf: isUser ? "flex-end" : "flex-start" }}
    >
      <Stack gap={4}>
        <Text size="xs" fw={600} c={isUser ? "steel.3" : "dimmed"}>
          {isUser ? "You" : "Assistant"}
          {msg.isStreaming && " ●"}
        </Text>

        {/* Thinking content */}
        {msg.thinkingContent && (
          <>
            <Group
              gap={4}
              style={{ cursor: "pointer" }}
              onClick={() => setThinkingOpen((o) => !o)}
            >
              {thinkingOpen ? (
                <IconChevronDown size={12} />
              ) : (
                <IconChevronRight size={12} />
              )}
              <Text size="xs" c="dimmed" fs="italic">
                Thinking…
              </Text>
            </Group>
            <Collapse in={thinkingOpen}>
              <Text
                size="xs"
                c="dimmed"
                fs="italic"
                style={{ whiteSpace: "pre-wrap" }}
              >
                {msg.thinkingContent}
              </Text>
            </Collapse>
          </>
        )}

        {/* Tool calls */}
        {msg.toolCalls && msg.toolCalls.length > 0 && (
          <Stack gap={4}>
            {msg.toolCalls.map((tc, i) => (
              <ToolCallRow key={i} tc={tc} />
            ))}
          </Stack>
        )}

        {/* Main content */}
        <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
          {msg.content}
          {msg.isStreaming && !msg.content && "…"}
        </Text>

        {/* Actions for assistant messages */}
        {!isUser && !msg.isStreaming && msg.content && (
          <Group gap="xs">
            <ActionIcon
              variant="subtle"
              color="green"
              size="sm"
              title="Apply (replace document)"
              onClick={() => onApply(msg.content)}
            >
              <IconCheck size={14} />
            </ActionIcon>
            <ActionIcon
              variant="subtle"
              color="blue"
              size="sm"
              title="Append to document"
              onClick={() => onAppend(msg.content)}
            >
              <IconPlus size={14} />
            </ActionIcon>
            <ActionIcon
              variant="subtle"
              color="grape"
              size="sm"
              title="Regenerate from here"
              onClick={() => onRegenerate(msg.id)}
            >
              <IconRefresh size={14} />
            </ActionIcon>
            <ActionIcon
              variant="subtle"
              color="red"
              size="sm"
              title="Delete message"
              onClick={() => onDelete(msg.id)}
            >
              <IconTrash size={14} />
            </ActionIcon>
          </Group>
        )}
      </Stack>
    </Paper>
  );
});

// ---------------------------------------------------------------------------
// ToolCallRow sub-component
// ---------------------------------------------------------------------------

function formatArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(", ");
}

const ToolCallRow = observer(function ToolCallRow({ tc }: { tc: ToolCallEntry }) {
  const [open, setOpen] = useState(false);
  const pending = tc.result === undefined;

  return (
    <Paper p={6} withBorder bg="dark.7">
      <Group
        gap={4}
        style={{ cursor: pending ? "default" : "pointer" }}
        onClick={() => !pending && setOpen((o) => !o)}
      >
        {!pending && (
          open ? <IconChevronDown size={11} /> : <IconChevronRight size={11} />
        )}
        <Text size="xs" c="teal.3" fw={600} style={{ fontFamily: "monospace" }}>
          {tc.tool_name}({formatArgs(tc.arguments)})
        </Text>
        {pending && (
          <Text size="xs" c="dimmed" fs="italic">running…</Text>
        )}
      </Group>
      <Collapse in={open}>
        <Text
          size="xs"
          c="dimmed"
          mt={4}
          style={{ whiteSpace: "pre-wrap", maxHeight: 160, overflow: "auto" }}
        >
          {tc.result}
        </Text>
      </Collapse>
    </Paper>
  );
});
