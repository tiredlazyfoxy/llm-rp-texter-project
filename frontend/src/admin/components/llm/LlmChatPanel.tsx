import { useCallback, useEffect, useRef, useState } from "react";
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
import type {
  ChatMessage,
  EditorLlmParams,
  LlmChatRequest,
  SSEHandlers,
  ToolCallEntry,
} from "../../../types/llmChat";
import type { EnabledModelInfo } from "../../../types/llmServer";
import { fetchEnabledModels, streamChat, translateTextAdmin } from "../../../api/llmChat";
import { LlmInputBar } from "../../../components/LlmInputBar";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LS_MODEL_KEY = "llmrp_editor_model";
const LS_PARAMS_KEY = "llmrp_editor_params";

const DEFAULT_PARAMS: EditorLlmParams = {
  temperature: 0.7,
  top_p: 1.0,
  repetition_penalty: 1.0,
  enable_thinking: false,
  enable_tools: false,
};

function loadParams(): EditorLlmParams {
  try {
    const raw = localStorage.getItem(LS_PARAMS_KEY);
    if (raw) return { ...DEFAULT_PARAMS, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return { ...DEFAULT_PARAMS };
}

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

export function LlmChatPanel({
  currentContent,
  worldId,
  docId,
  docType,
  fieldType,
  onApply,
  onAppend,
}: LlmChatPanelProps) {
  // Models
  const [models, setModels] = useState<EnabledModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<string | null>(
    () => localStorage.getItem(LS_MODEL_KEY),
  );

  // Params
  const [params, setParams] = useState<EditorLlmParams>(loadParams);
  const [paramsOpen, setParamsOpen] = useState(false);

  // Chat
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  // Refs
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const streamMsgRef = useRef<ChatMessage | null>(null);
  const isAtBottom = useRef(true);

  // ---- Load models on mount ------------------------------------------------

  useEffect(() => {
    fetchEnabledModels()
      .then((list) => {
        setModels(list);
        // If saved model no longer available, clear selection
        const saved = localStorage.getItem(LS_MODEL_KEY);
        if (saved && !list.some((m) => m.model_id === saved)) {
          setSelectedModel(null);
          localStorage.removeItem(LS_MODEL_KEY);
        }
      })
      .catch(() => {});
  }, []);

  // ---- Persist model selection ---------------------------------------------

  useEffect(() => {
    if (selectedModel) localStorage.setItem(LS_MODEL_KEY, selectedModel);
    else localStorage.removeItem(LS_MODEL_KEY);
  }, [selectedModel]);

  // ---- Persist params ------------------------------------------------------

  useEffect(() => {
    localStorage.setItem(LS_PARAMS_KEY, JSON.stringify(params));
  }, [params]);

  // ---- Auto-scroll ---------------------------------------------------------

  const scrollToBottom = useCallback(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, []);

  // Track whether user is near the bottom
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const handleScroll = () => {
      isAtBottom.current = el.scrollTop + el.clientHeight >= el.scrollHeight - 40;
    };
    el.addEventListener("scroll", handleScroll);
    return () => el.removeEventListener("scroll", handleScroll);
  }, []);

  // Only auto-scroll when at bottom
  useEffect(() => {
    if (isAtBottom.current) scrollToBottom();
  }, [messages, scrollToBottom]);

  // ---- Streaming -----------------------------------------------------------

  const doStream = useCallback(
    (chatMessages: ChatMessage[]) => {
      if (!selectedModel) return;

      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "",
        thinkingContent: "",
        isStreaming: true,
      };
      streamMsgRef.current = assistantMsg;
      const updatedMessages = [...chatMessages, assistantMsg];
      setMessages(updatedMessages);
      setIsStreaming(true);

      const apiMessages = updatedMessages
        .filter((m) => !m.isStreaming)
        .map((m) => ({ role: m.role, content: m.content }));

      const request: LlmChatRequest = {
        model_id: selectedModel,
        messages: apiMessages,
        temperature: params.temperature,
        top_p: params.top_p,
        repetition_penalty: params.repetition_penalty,
        enable_thinking: params.enable_thinking,
        enable_tools: params.enable_tools,
        current_content: currentContent,
        world_id: worldId ?? null,
        doc_id: docId ?? "",
        doc_type: docType ?? "",
        field_type: fieldType ?? "",
      };

      const handlers: SSEHandlers = {
        onToken: (content) => {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (!last || last.role !== "assistant") return prev;
            const updated = { ...last, content: last.content + content };
            streamMsgRef.current = updated;
            return [...prev.slice(0, -1), updated];
          });
        },
        onThinking: (content) => {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (!last || last.role !== "assistant") return prev;
            const updated = {
              ...last,
              thinkingContent: (last.thinkingContent || "") + content,
            };
            streamMsgRef.current = updated;
            return [...prev.slice(0, -1), updated];
          });
        },
        onThinkingDone: () => {
          // No-op — thinking content is already accumulated
        },
        onToolCallStart: (tool_name, args) => {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (!last || last.role !== "assistant") return prev;
            const entry: ToolCallEntry = { tool_name, arguments: args };
            const updated = {
              ...last,
              toolCalls: [...(last.toolCalls ?? []), entry],
            };
            streamMsgRef.current = updated;
            return [...prev.slice(0, -1), updated];
          });
        },
        onToolCallResult: (tool_name, result) => {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (!last || last.role !== "assistant") return prev;
            const calls = [...(last.toolCalls ?? [])];
            // Attach result to the last call with this tool_name that has no result yet
            const idx = calls.findLastIndex(
              (c) => c.tool_name === tool_name && c.result === undefined,
            );
            if (idx !== -1) calls[idx] = { ...calls[idx], result };
            const updated = { ...last, toolCalls: calls };
            streamMsgRef.current = updated;
            return [...prev.slice(0, -1), updated];
          });
        },
        onDone: (content) => {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (!last || last.role !== "assistant") return prev;
            return [
              ...prev.slice(0, -1),
              { ...last, content, isStreaming: false },
            ];
          });
          setIsStreaming(false);
          streamMsgRef.current = null;
          abortRef.current = null;
        },
        onError: (message) => {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (!last || last.role !== "assistant") return prev;
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                content: last.content || `Error: ${message}`,
                isStreaming: false,
              },
            ];
          });
          setIsStreaming(false);
          streamMsgRef.current = null;
          abortRef.current = null;
        },
      };

      abortRef.current = streamChat(request, handlers);
    },
    [selectedModel, params, currentContent, worldId, docId, docType, fieldType],
  );

  // ---- Actions -------------------------------------------------------------

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming || !selectedModel) return;
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setInput("");
    isAtBottom.current = true;
    doStream(updated);
  }, [input, isStreaming, selectedModel, messages, doStream]);

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (!last || last.role !== "assistant") return prev;
      return [...prev.slice(0, -1), { ...last, isStreaming: false }];
    });
    setIsStreaming(false);
    streamMsgRef.current = null;
    abortRef.current = null;
  }, []);

  const handleDelete = useCallback((id: string) => {
    setMessages((prev) => prev.filter((m) => m.id !== id));
  }, []);

  const handleRegenerate = useCallback(() => {
    if (isStreaming) return;
    // Remove last assistant message and re-stream
    setMessages((prev) => {
      const withoutLast =
        prev.length > 0 && prev[prev.length - 1].role === "assistant"
          ? prev.slice(0, -1)
          : prev;
      // Trigger stream after state update
      setTimeout(() => doStream(withoutLast), 0);
      return withoutLast;
    });
  }, [isStreaming, doStream]);

  const handleRegenerateMsg = useCallback(
    (id: string) => {
      if (isStreaming) return;
      setMessages((prev) => {
        const idx = prev.findIndex((m) => m.id === id);
        if (idx === -1) return prev;
        const truncated = prev.slice(0, idx);
        setTimeout(() => doStream(truncated), 0);
        return truncated;
      });
    },
    [isStreaming, doStream],
  );

  const handleClear = useCallback(() => {
    if (isStreaming) handleStop();
    setMessages([]);
  }, [isStreaming, handleStop]);

  // ---- Model select data ---------------------------------------------------

  const modelOptions = models.map((m) => ({
    value: m.model_id,
    label: `${m.model_id} (${m.server_name})`,
  }));

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
              onClick={() => setParamsOpen((o) => !o)}
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
          data={modelOptions}
          value={selectedModel}
          onChange={setSelectedModel}
          searchable
          size="sm"
        />

        {/* Parameters */}
        <Collapse in={paramsOpen}>
          <Paper p="sm" withBorder>
            <Stack gap="xs">
              <Text size="xs" fw={600}>Temperature ({params.temperature})</Text>
              <Slider
                min={0} max={2} step={0.1}
                value={params.temperature}
                onChange={(v) => setParams((p) => ({ ...p, temperature: v }))}
              />
              <Text size="xs" fw={600}>Top-p ({params.top_p})</Text>
              <Slider
                min={0} max={1} step={0.05}
                value={params.top_p}
                onChange={(v) => setParams((p) => ({ ...p, top_p: v }))}
              />
              <Text size="xs" fw={600}>
                Repetition penalty ({params.repetition_penalty})
              </Text>
              <Slider
                min={1} max={2} step={0.05}
                value={params.repetition_penalty}
                onChange={(v) =>
                  setParams((p) => ({ ...p, repetition_penalty: v }))
                }
              />
              <Switch
                label="Thinking mode"
                checked={params.enable_thinking}
                onChange={(e) => {
                  const checked = e.currentTarget.checked;
                  setParams((p) => ({ ...p, enable_thinking: checked }));
                }}
              />
              <Switch
                label="Use tools (search, lore, web)"
                checked={params.enable_tools}
                onChange={(e) => {
                  const checked = e.currentTarget.checked;
                  setParams((p) => ({ ...p, enable_tools: checked }));
                }}
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
            {messages.length === 0 && (
              <Text c="dimmed" ta="center" size="sm" py="xl">
                Send a message to start chatting with the LLM.
              </Text>
            )}
            {messages.map((msg) => (
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
          busy={isStreaming}
          onSend={handleSend}
          onStop={handleStop}
          disabled={!selectedModel}
          placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
          textareaProps={{
            autosize: true,
            minRows: 1,
            maxRows: 5,
            style: { flex: 1 },
          }}
        />

        {/* Regenerate — only when last message is a completed assistant message */}
        {messages.length > 0 &&
          messages[messages.length - 1].role === "assistant" &&
          !messages[messages.length - 1].isStreaming && (
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
}

// ---------------------------------------------------------------------------
// MessageBubble sub-component
// ---------------------------------------------------------------------------

function MessageBubble({
  msg,
  onApply,
  onAppend,
  onDelete,
  onRegenerate,
}: {
  msg: ChatMessage;
  onApply: (content: string) => void;
  onAppend: (content: string) => void;
  onDelete: (id: string) => void;
  onRegenerate: (id: string) => void;
}) {
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

        {/* Tool calls — one row per call, result collapsed by default */}
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
}

// ---------------------------------------------------------------------------
// ToolCallRow sub-component
// ---------------------------------------------------------------------------

function formatArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(", ");
}

function ToolCallRow({ tc }: { tc: ToolCallEntry }) {
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
}
