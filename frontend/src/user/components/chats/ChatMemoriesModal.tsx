import { useEffect, useState } from "react";
import {
  ActionIcon,
  Collapse,
  Group,
  Modal,
  Stack,
  Text,
  Tooltip,
} from "@mantine/core";
import { IconBrain, IconChevronDown, IconChevronRight, IconTrash } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import { chatStore } from "../../stores/ChatStore";
import { formatDate } from "../../../utils/formatDate";

export const ChatMemoriesButton = observer(function ChatMemoriesButton() {
  const [opened, setOpened] = useState(false);

  function handleOpen() {
    chatStore.loadMemories().catch(() => {});
    setOpened(true);
  }

  return (
    <>
      <Tooltip label="Memory" position="bottom">
        <ActionIcon variant="subtle" color="gray" size="md" onClick={handleOpen}>
          <IconBrain size={18} />
        </ActionIcon>
      </Tooltip>
      <ChatMemoriesModal opened={opened} onClose={() => setOpened(false)} />
    </>
  );
});

interface ChatMemoriesModalProps {
  opened: boolean;
  onClose: () => void;
}

const ChatMemoriesModal = observer(function ChatMemoriesModal({ opened, onClose }: ChatMemoriesModalProps) {
  const memories = chatStore.memories;
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (opened) chatStore.loadMemories().catch(() => {});
  }, [opened]);

  function toggleExpand(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Chat Memory" size="70%">
      {memories.length === 0 ? (
        <Text c="dimmed" size="sm" ta="center" py="lg">
          No memories yet
        </Text>
      ) : (
        <Stack gap="xs">
          {memories.map((mem) => {
            const isExpanded = expanded.has(mem.id);
            const preview = mem.content.length > 400 ? mem.content.slice(0, 400) + "…" : mem.content;

            return (
              <div
                key={mem.id}
                style={{
                  border: "1px solid var(--mantine-color-dark-4)",
                  borderRadius: "var(--mantine-radius-sm)",
                  padding: "8px 12px",
                }}
              >
                <Group justify="space-between" wrap="nowrap">
                  <Group gap="xs" wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
                    <UnstyledToggle onClick={() => toggleExpand(mem.id)}>
                      {isExpanded
                        ? <IconChevronDown size={14} />
                        : <IconChevronRight size={14} />
                      }
                    </UnstyledToggle>
                    <Text size="xs" c="dimmed">{formatDate(mem.created_at)}</Text>
                  </Group>

                  <ActionIcon
                    variant="subtle"
                    color="red"
                    size="sm"
                    onClick={() => chatStore.deleteMemory(mem.id)}
                  >
                    <IconTrash size={14} />
                  </ActionIcon>
                </Group>

                <Collapse in={isExpanded}>
                  <Text size="sm" mt="xs" style={{ whiteSpace: "pre-wrap" }}>
                    {mem.content}
                  </Text>
                </Collapse>
                {!isExpanded && (
                  <Text size="xs" c="dimmed" mt={4} style={{ cursor: "pointer" }} onClick={() => toggleExpand(mem.id)}>
                    {preview}
                  </Text>
                )}
              </div>
            );
          })}
        </Stack>
      )}
    </Modal>
  );
});

function UnstyledToggle({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <span onClick={onClick} style={{ cursor: "pointer", display: "flex", alignItems: "center", color: "var(--mantine-color-dimmed)" }}>
      {children}
    </span>
  );
}
