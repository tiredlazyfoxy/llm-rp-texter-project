import { Badge, Collapse, Group, Progress, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";
import { observer } from "mobx-react-lite";
import { useState } from "react";
import { ChatPageState } from "../../pages/chatPageState";

function StatRow({
  name,
  value,
  def,
  isHidden,
}: {
  name: string;
  value: number | string | string[];
  def: StatDefinition | undefined;
  isHidden?: boolean;
}) {
  const opacity = isHidden ? 0.5 : 1;
  if (def?.stat_type === "int" && typeof value === "number") {
    const min = def.min_value ?? 0;
    const max = def.max_value ?? 100;
    const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
    return (
      <Stack gap={2} style={{ opacity }}>
        <Group justify="space-between">
          <Text size="xs" c="dimmed">{name}{isHidden ? " (hidden)" : ""}</Text>
          <Text size="xs">{value}</Text>
        </Group>
        <Progress value={pct} size="xs" />
      </Stack>
    );
  }

  if (def?.stat_type === "set" && Array.isArray(value)) {
    return (
      <Stack gap={2} style={{ opacity }}>
        <Text size="xs" c="dimmed">{name}{isHidden ? " (hidden)" : ""}</Text>
        <Group gap={4}>
          {value.map((v) => <Badge key={v} size="xs" variant="light">{v}</Badge>)}
          {value.length === 0 && <Text size="xs" c="dimmed">—</Text>}
        </Group>
      </Stack>
    );
  }

  return (
    <Group justify="space-between" style={{ opacity }}>
      <Text size="xs" c="dimmed">{name}{isHidden ? " (hidden)" : ""}</Text>
      <Badge size="xs" variant="light">{String(value)}</Badge>
    </Group>
  );
}

interface StatsPanelProps {
  state: ChatPageState;
}

export const StatsPanel = observer(function StatsPanel({ state }: StatsPanelProps) {
  const [charOpen, setCharOpen] = useState(true);
  const [worldOpen, setWorldOpen] = useState(false);
  const snap = state.displaySnapshot;
  const statDefs = state.world?.stat_definitions ?? [];

  if (!snap) return null;

  const charStats = snap.character_stats;
  const worldStats = snap.world_stats;
  const charDefs = statDefs.filter((d) => d.scope === "character");
  const worldDefs = statDefs.filter((d) => d.scope === "world");

  return (
    <Stack gap="xs" p="sm" style={{ width: 200, flexShrink: 0, borderLeft: "1px solid var(--mantine-color-dark-4)", overflowY: "auto" }}>
      {snap.location_name && (
        <Text size="xs" c="dimmed">📍 {snap.location_name}</Text>
      )}

      <UnstyledButton onClick={() => setCharOpen((o) => !o)}>
        <Group gap={4}>
          {charOpen ? <IconChevronDown size={12} /> : <IconChevronRight size={12} />}
          <Text size="xs" fw={600} c="dimmed">Character</Text>
        </Group>
      </UnstyledButton>
      <Collapse in={charOpen}>
        <Stack gap="xs">
          {Object.entries(charStats).map(([k, v]) => (
            <StatRow key={k} name={k} value={v} def={charDefs.find((d) => d.name === k)} isHidden={charDefs.find((d) => d.name === k)?.hidden} />
          ))}
          {Object.keys(charStats).length === 0 && (
            <Text size="xs" c="dimmed">No stats</Text>
          )}
        </Stack>
      </Collapse>

      <UnstyledButton onClick={() => setWorldOpen((o) => !o)}>
        <Group gap={4}>
          {worldOpen ? <IconChevronDown size={12} /> : <IconChevronRight size={12} />}
          <Text size="xs" fw={600} c="dimmed">World</Text>
        </Group>
      </UnstyledButton>
      <Collapse in={worldOpen}>
        <Stack gap="xs">
          {Object.entries(worldStats).map(([k, v]) => (
            <StatRow key={k} name={k} value={v} def={worldDefs.find((d) => d.name === k)} isHidden={worldDefs.find((d) => d.name === k)?.hidden} />
          ))}
          {Object.keys(worldStats).length === 0 && (
            <Text size="xs" c="dimmed">No stats</Text>
          )}
        </Stack>
      </Collapse>
    </Stack>
  );
});
