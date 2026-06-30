import { useEffect, useState } from "react";
import { ActionIcon, Badge, Button, Group, Loader, Stack, Text, Textarea, Tooltip } from "@mantine/core";
import { IconGripHorizontal, IconMessage, IconRefresh, IconThumbDown } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import { translateTextChat } from "../../../api/chat";
import { LlmInputBar } from "../../../components/LlmInputBar";
import { extractUserInstructions } from "../../../utils/oocParser";
import {
  ChatPageState,
  fastReject,
  regenerate,
  rejectWithComment,
  sendMessage,
  stopGeneration,
} from "../../pages/chatPageState";

const STORAGE_KEY = "chatInputHeight";
const DEFAULT_HEIGHT = 120;
const MIN_HEIGHT = 60;

function loadHeight(): number {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored ? Math.max(MIN_HEIGHT, Number(stored)) : DEFAULT_HEIGHT;
}

interface ChatInputProps {
  state: ChatPageState;
}

export const ChatInput = observer(function ChatInput({ state }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [height, setHeight] = useState(loadHeight);
  const disabled = state.currentChat?.session.status !== "active";

  // Clear local input when backend ack clears pendingInput
  useEffect(() => {
    if (!state.pendingInput && state.isSending) {
      setValue("");
    }
  }, [state.pendingInput]);

  function handleResizeStart(e: React.PointerEvent) {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = height;
    const maxHeight = window.innerHeight * 0.7;

    function onMove(ev: PointerEvent) {
      const delta = startY - ev.clientY;
      const next = Math.min(maxHeight, Math.max(MIN_HEIGHT, startHeight + delta));
      setHeight(next);
    }
    function onUp() {
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      // persist after drag ends
      setHeight((h) => { localStorage.setItem(STORAGE_KEY, String(Math.round(h))); return h; });
    }
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
  }

  const oocPreview = extractUserInstructions(value).userInstructions;
  const isChainMode = state.world?.generation_mode === "chain";
  const latestAssistantContent =
    state.activeMessages.findLast((m) => m.role === "assistant")?.content ?? "";

  async function handleSend() {
    const text = value.trim();
    if (!text || state.isSending) return;
    const { content, userInstructions } = extractUserInstructions(text);
    await sendMessage(state, content, userInstructions ?? undefined);
  }

  async function handleRegenerate() {
    if (state.isSending) return;
    await regenerate(state);
  }

  const before = (
    <>
      {oocPreview && (
        <Text
          size="xs" c="dimmed" fs="italic" mb={4}
          style={{ borderLeft: "2px solid var(--mantine-color-violet-7)", paddingLeft: 8 }}
        >
          OOC: {oocPreview}
        </Text>
      )}
      {state.isSending && state.currentStatus && (
        <Group gap="xs" mb={4} align="center">
          <Loader size={12} />
          {state.currentPhase && (
            <Badge size="xs" variant="light" color={state.currentPhase === "planning" ? "violet" : "teal"}>
              {state.currentPhase === "planning" ? "Planning" : "Writing"}
            </Badge>
          )}
          <Text size="xs" c="dimmed">{state.currentStatus}</Text>
        </Group>
      )}
      {isChainMode && !state.isSending && state.rejectCommentOpen && (
        <Stack gap="xs" mb={6}>
          <Text size="xs" c="dimmed" fw={600}>Rejected generation</Text>
          <Text
            size="xs"
            c="dimmed"
            style={{
              whiteSpace: "pre-wrap",
              maxHeight: 160,
              overflow: "auto",
              borderLeft: "2px solid var(--mantine-color-dark-4)",
              paddingLeft: 8,
            }}
          >
            {latestAssistantContent}
          </Text>
          <Textarea
            placeholder="What's wrong with this generation? (sent with the re-plan)"
            value={state.rejectComment}
            onChange={(e) => { state.rejectComment = e.currentTarget.value; }}
            minRows={2}
            maxRows={6}
            autosize
            size="xs"
          />
          <Group gap="xs">
            <Button size="xs" disabled={disabled} onClick={() => rejectWithComment(state)}>
              Submit reject
            </Button>
            <Button size="xs" variant="subtle" onClick={() => { state.rejectCommentOpen = false; }}>
              Cancel
            </Button>
          </Group>
        </Stack>
      )}
    </>
  );

  const showRegenerate =
    !state.isSending && state.activeMessages.some((m) => m.role === "assistant");

  const extras = showRegenerate ? (
    isChainMode ? (
      <Group gap={4}>
        <Tooltip label="Reject — bad plan, redo the whole chain">
          <ActionIcon variant="subtle" size="lg" onClick={() => fastReject(state, "plan")} disabled={disabled}>
            <IconThumbDown size={18} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="Reject generation — plan is fine, rewrite the text">
          <ActionIcon variant="subtle" size="lg" onClick={() => fastReject(state, "text")} disabled={disabled}>
            <IconRefresh size={18} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="Reject with comment">
          <ActionIcon
            variant="subtle" size="lg"
            onClick={() => { state.rejectCommentOpen = !state.rejectCommentOpen; }}
            disabled={disabled}
          >
            <IconMessage size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>
    ) : (
      <Tooltip label="Regenerate">
        <ActionIcon variant="subtle" size="lg" onClick={handleRegenerate} disabled={disabled}>
          <IconRefresh size={18} />
        </ActionIcon>
      </Tooltip>
    )
  ) : undefined;

  return (
    <div style={{ height, flexShrink: 0, display: "flex", flexDirection: "column", borderTop: "1px solid var(--mantine-color-dark-4)" }}>
      {/* Resize handle */}
      <div
        onPointerDown={handleResizeStart}
        style={{
          display: "flex", justifyContent: "center", alignItems: "center",
          height: 12, cursor: "ns-resize", flexShrink: 0,
          color: "var(--mantine-color-dimmed)",
        }}
      >
        <IconGripHorizontal size={14} />
      </div>

      <div style={{ padding: "0 12px 8px", flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <LlmInputBar
          value={value}
          onChange={setValue}
          translateFn={translateTextChat}
          busy={state.isSending}
          onSend={handleSend}
          onStop={() => stopGeneration(state)}
          disabled={disabled}
          placeholder={disabled ? "Chat archived" : "Type your message… (Enter to send, Shift+Enter for newline)"}
          before={before}
          extras={extras}
          textareaProps={{
            styles: {
              root: { flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" },
              input: { flex: 1, overflow: "auto" },
            },
          }}
        />
      </div>
    </div>
  );
});
