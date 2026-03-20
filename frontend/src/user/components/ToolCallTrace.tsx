import { useState } from "react";
import { Collapse, Group, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconChevronDown, IconChevronRight, IconTool } from "@tabler/icons-react";

interface ToolCallTraceProps {
  toolCalls: ToolCallInfo[];
}

export function ToolCallTrace({ toolCalls }: ToolCallTraceProps) {
  const [open, setOpen] = useState(false);

  if (toolCalls.length === 0) return null;

  return (
    <div style={{ marginTop: 8 }}>
      <UnstyledButton onClick={() => setOpen((o) => !o)}>
        <Group gap={4}>
          <IconTool size={12} color="var(--mantine-color-dimmed)" />
          <Text size="xs" c="dimmed">
            {toolCalls.length} tool call{toolCalls.length > 1 ? "s" : ""}
          </Text>
          {open ? <IconChevronDown size={12} /> : <IconChevronRight size={12} />}
        </Group>
      </UnstyledButton>
      <Collapse in={open}>
        <Stack gap="xs" mt="xs" pl="sm" style={{ borderLeft: "2px solid var(--mantine-color-dark-4)" }}>
          {toolCalls.map((tc, i) => (
            <div key={i}>
              <Text size="xs" fw={600} c="dimmed">{tc.tool_name}</Text>
              <Text size="xs" c="dimmed" style={{ fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
                {JSON.stringify(tc.arguments, null, 2)}
              </Text>
              {tc.result && (
                <Text size="xs" c="dimmed" style={{ fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
                  → {tc.result.length > 200 ? tc.result.slice(0, 200) + "…" : tc.result}
                </Text>
              )}
            </div>
          ))}
        </Stack>
      </Collapse>
    </div>
  );
}
