import { Badge, Group, Paper, Text, Tooltip } from "@mantine/core";
import type { PlaceholderInfo } from "../../types/world";

interface PlaceholderPanelProps {
  placeholders: PlaceholderInfo[];
  content: string;
  onInsert: (name: string) => void;
}

export function PlaceholderPanel({ placeholders, content, onInsert }: PlaceholderPanelProps) {
  return (
    <Paper p="xs" withBorder>
      <Text size="xs" c="dimmed" mb={4}>Placeholders</Text>
      <Group gap={4}>
        {placeholders.map(p => {
          const used = content.includes(`{${p.name}}`);
          return (
            <Tooltip key={p.name} label={p.description} withArrow>
              <Badge
                size="sm"
                variant={used ? "filled" : "outline"}
                color={used ? "green.8" : "gray"}
                style={{ cursor: "pointer" }}
                onClick={() => onInsert(p.name)}
              >
                {p.name}
              </Badge>
            </Tooltip>
          );
        })}
      </Group>
    </Paper>
  );
}
