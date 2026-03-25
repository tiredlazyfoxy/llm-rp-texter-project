import { Paper, Text, Group, Badge, Stack } from "@mantine/core";
import type { PlaceholderInfo } from "../../types/world";
import type { AutocompletePosition } from "../hooks/usePlaceholderAutocomplete";

interface PlaceholderSuggestionsProps {
  visible: boolean;
  suggestions: PlaceholderInfo[];
  selectedIndex: number;
  position: AutocompletePosition;
  onSelect: (index: number) => void;
}

export function PlaceholderSuggestions({
  visible,
  suggestions,
  selectedIndex,
  position,
  onSelect,
}: PlaceholderSuggestionsProps) {
  if (!visible || suggestions.length === 0) return null;

  return (
    <Paper
      shadow="md"
      p={4}
      withBorder
      style={{
        position: "fixed",
        top: position.top,
        left: position.left,
        zIndex: 1000,
        maxHeight: 260,
        overflowY: "auto",
        width: 400,
      }}
    >
      <Stack gap={0}>
        {suggestions.map((p, i) => (
          <Group
            key={p.name}
            gap="xs"
            px="xs"
            py={4}
            wrap="nowrap"
            style={{
              cursor: "pointer",
              borderRadius: 4,
              backgroundColor: i === selectedIndex
                ? "var(--mantine-color-blue-light)"
                : undefined,
            }}
            onMouseDown={(e) => {
              e.preventDefault(); // keep textarea focused
              onSelect(i);
            }}
          >
            <Badge size="sm" variant="outline" style={{ flexShrink: 0 }}>
              {`{${p.name}}`}
            </Badge>
            <Text size="xs" c="dimmed" lineClamp={1}>
              {p.description}
            </Text>
          </Group>
        ))}
      </Stack>
    </Paper>
  );
}
