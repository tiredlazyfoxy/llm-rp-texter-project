import { Badge, Group, Paper, Stack, Text, Tooltip } from "@mantine/core";
import type { PlaceholderInfo } from "../../../types/pipeline";
import type { StatPlaceholder } from "./buildStatPlaceholders";

interface PlaceholderPanelProps {
  placeholders: PlaceholderInfo[];
  content: string;
  onInsert: (name: string) => void;
  /**
   * Optional namespaced stat placeholders sourced from
   * `WorldStatDefinition`. Rendered under a "Stats" subheading
   * below the regular placeholders. Click inserts the unbraced
   * label (`USER:HEALTH`) — `onInsert` adds the braces.
   */
  statPlaceholders?: StatPlaceholder[];
}

export function PlaceholderPanel({
  placeholders,
  content,
  onInsert,
  statPlaceholders,
}: PlaceholderPanelProps) {
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
      {statPlaceholders && statPlaceholders.length > 0 && (
        <Stack gap={4} mt="xs">
          <Text size="xs" c="dimmed">Stats</Text>
          <Group gap={4}>
            {statPlaceholders.map(s => {
              const used = content.includes(s.token);
              const tooltip = `Live ${s.owner} stat (${s.kind}${s.hidden ? ", hidden" : ""})`;
              return (
                <Tooltip key={s.label} label={tooltip} withArrow>
                  <Badge
                    size="sm"
                    variant={used ? "filled" : "outline"}
                    color={used ? "green.8" : "gray"}
                    style={{ cursor: "pointer" }}
                    onClick={() => onInsert(s.label)}
                  >
                    {s.label}
                  </Badge>
                </Tooltip>
              );
            })}
          </Group>
        </Stack>
      )}
    </Paper>
  );
}
