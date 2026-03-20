import { useState } from "react";
import { Button, Group, Paper, Text } from "@mantine/core";
import { IconChevronLeft, IconChevronRight } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import { chatStore } from "../stores/ChatStore";

export const VariantSelector = observer(function VariantSelector() {
  const [index, setIndex] = useState(0);
  const variants = chatStore.latestTurnVariants;

  if (!chatStore.hasMultipleVariants) return null;

  const current = variants[index];
  if (!current) return null;

  async function handleContinue() {
    await chatStore.continueWithVariant(current.id);
  }

  return (
    <Paper p="sm" radius="sm" withBorder style={{ margin: "8px 16px" }}>
      <Group justify="space-between" mb="xs">
        <Text size="xs" c="dimmed">
          Variant {index + 1} / {variants.length}
        </Text>
        <Group gap="xs">
          <Button
            size="xs"
            variant="subtle"
            disabled={index === 0}
            onClick={() => setIndex((i) => i - 1)}
            px={6}
          >
            <IconChevronLeft size={14} />
          </Button>
          <Button
            size="xs"
            variant="subtle"
            disabled={index === variants.length - 1}
            onClick={() => setIndex((i) => i + 1)}
            px={6}
          >
            <IconChevronRight size={14} />
          </Button>
        </Group>
      </Group>
      <Text size="sm" lineClamp={3} style={{ whiteSpace: "pre-wrap" }}>
        {current.content}
      </Text>
      <Group justify="flex-end" mt="xs">
        <Button size="xs" onClick={handleContinue}>
          Continue with this
        </Button>
      </Group>
    </Paper>
  );
});
