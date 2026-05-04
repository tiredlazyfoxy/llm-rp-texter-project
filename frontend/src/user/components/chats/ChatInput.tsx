import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActionIcon, Badge, Group, Loader, Text, Textarea, Tooltip } from "@mantine/core";
import { IconArrowBackUp, IconGripHorizontal, IconLanguage, IconPlayerStop, IconRefresh, IconSend } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import { translateTextChat } from "../../api/chat";
import { useTranslation } from "../../hooks/useTranslation";
import { extractUserInstructions } from "../../utils/oocParser";
import { chatStore } from "../stores/ChatStore";

const STORAGE_KEY = "chatInputHeight";
const DEFAULT_HEIGHT = 120;
const MIN_HEIGHT = 60;

function loadHeight(): number {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored ? Math.max(MIN_HEIGHT, Number(stored)) : DEFAULT_HEIGHT;
}

export const ChatInput = observer(function ChatInput() {
  const [value, setValue] = useState("");
  const [height, setHeight] = useState(loadHeight);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const disabled = chatStore.currentChat?.session.status !== "active";

  // Clear local input when backend ack clears pendingInput
  useEffect(() => {
    if (!chatStore.pendingInput && chatStore.isSending) {
      setValue("");
    }
  }, [chatStore.pendingInput]);

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

  const oocPreview = useMemo(() => extractUserInstructions(value).userInstructions, [value]);

  const getValue = useCallback(() => value, [value]);
  const { isTranslating, canRevert, translateError, handleTranslate, handleRevert, onInputChange, clearTranslateError } = useTranslation({
    getValue,
    setValue,
    translateFn: translateTextChat,
  });

  async function handleSend() {
    const text = value.trim();
    if (!text || chatStore.isSending) return;
    const { content, userInstructions } = extractUserInstructions(text);
    await chatStore.sendMessage(content, userInstructions ?? undefined);
  }

  async function handleRegenerate() {
    if (chatStore.isSending) return;
    await chatStore.regenerate();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div ref={containerRef} style={{ height, flexShrink: 0, display: "flex", flexDirection: "column", borderTop: "1px solid var(--mantine-color-dark-4)" }}>
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
        {oocPreview && (
          <Text
            size="xs" c="dimmed" fs="italic" mb={4}
            style={{ borderLeft: "2px solid var(--mantine-color-violet-7)", paddingLeft: 8 }}
          >
            OOC: {oocPreview}
          </Text>
        )}
        {translateError && (
          <Text size="xs" c="red" mb={4} onClick={clearTranslateError} style={{ cursor: "pointer" }}>
            {translateError}
          </Text>
        )}
        {chatStore.isSending && chatStore.currentStatus && (
          <Group gap="xs" mb={4} align="center">
            <Loader size={12} />
            {chatStore.currentPhase && (
              <Badge size="xs" variant="light" color={chatStore.currentPhase === "planning" ? "violet" : "teal"}>
                {chatStore.currentPhase === "planning" ? "Planning" : "Writing"}
              </Badge>
            )}
            <Text size="xs" c="dimmed">{chatStore.currentStatus}</Text>
          </Group>
        )}
        <Group align="flex-end" gap="xs" style={{ flex: 1, overflow: "hidden" }}>
          <Textarea
            ref={textareaRef}
            styles={{ root: { flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }, input: { flex: 1, overflow: "auto" } }}
            placeholder={disabled ? "Chat archived" : "Type your message… (Enter to send, Shift+Enter for newline)"}
            value={value}
            onChange={(e) => { setValue(e.target.value); onInputChange(e.target.value); }}
            onKeyDown={handleKeyDown}
            disabled={disabled || chatStore.isSending}
          />

        <Tooltip label="Translate to English">
          <ActionIcon
            variant="subtle"
            size="lg"
            onClick={handleTranslate}
            disabled={!value.trim() || disabled || chatStore.isSending || isTranslating}
            loading={isTranslating}
          >
            <IconLanguage size={18} />
          </ActionIcon>
        </Tooltip>

        {canRevert && (
          <Tooltip label="Revert to original">
            <ActionIcon variant="subtle" size="lg" color="orange" onClick={handleRevert}>
              <IconArrowBackUp size={18} />
            </ActionIcon>
          </Tooltip>
        )}

        {chatStore.isSending ? (
          <Tooltip label="Stop generation">
            <ActionIcon
              color="red"
              variant="filled"
              size="lg"
              onClick={() => chatStore.stopGeneration()}
            >
              <IconPlayerStop size={18} />
            </ActionIcon>
          </Tooltip>
        ) : (
          <Tooltip label="Send">
            <ActionIcon
              color="blue"
              variant="filled"
              size="lg"
              disabled={!value.trim() || disabled}
              onClick={handleSend}
            >
              <IconSend size={18} />
            </ActionIcon>
          </Tooltip>
        )}

        {!chatStore.isSending && chatStore.activeMessages.some((m) => m.role === "assistant") && (
          <Tooltip label="Regenerate">
            <ActionIcon variant="subtle" size="lg" onClick={handleRegenerate} disabled={disabled}>
              <IconRefresh size={18} />
            </ActionIcon>
          </Tooltip>
        )}
        </Group>
      </div>
    </div>
  );
});
