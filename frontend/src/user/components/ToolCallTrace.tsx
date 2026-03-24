import { useState } from "react";
import { Collapse, Group, Loader, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";

interface ToolCallTraceProps {
  toolCalls: ToolCallInfo[];
  debugMode?: boolean;
  streaming?: boolean;
}

/** Human-readable label for a tool call, e.g. `get location for "Brine House"` */
function formatToolLabel(tc: ToolCallInfo): string {
  const name = tc.tool_name
    .replace(/_/g, " ")
    .replace(/\binfo\b/, "")
    .replace(/\bimpl\b/, "")
    .trim();

  const query = tc.arguments?.query;
  if (query) return `${name} "${query}"`;

  // Fallback: show first argument value
  const vals = Object.values(tc.arguments ?? {});
  if (vals.length > 0) return `${name} "${vals[0]}"`;

  return name;
}

function ToolCallItem({ tc, debugMode, streaming }: { tc: ToolCallInfo; debugMode?: boolean; streaming?: boolean }) {
  const [open, setOpen] = useState(false);
  const hasResult = !!tc.result;

  return (
    <div>
      <UnstyledButton onClick={() => hasResult && setOpen((o) => !o)} style={{ cursor: hasResult ? "pointer" : "default" }}>
        <Group gap={4}>
          {streaming && !hasResult && <Loader size={10} />}
          {hasResult && (open ? <IconChevronDown size={10} /> : <IconChevronRight size={10} />)}
          <Text size="xs" c="dimmed">{formatToolLabel(tc)}</Text>
        </Group>
      </UnstyledButton>
      {hasResult && (
        <Collapse in={open}>
          {debugMode && (
            <Text size="xs" c="dimmed" mt={2} style={{ fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
              {JSON.stringify(tc.arguments, null, 2)}
            </Text>
          )}
          <div style={{ maxHeight: debugMode ? 300 : 150, overflow: "auto", marginTop: 2 }}>
            <Text size="xs" c="dimmed" style={{ fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
              {debugMode ? tc.result : (tc.result.length > 200 ? tc.result.slice(0, 200) + "\u2026" : tc.result)}
            </Text>
          </div>
        </Collapse>
      )}
    </div>
  );
}

export function ToolCallTrace({ toolCalls, debugMode, streaming }: ToolCallTraceProps) {
  if (toolCalls.length === 0) return null;

  return (
    <Stack gap={2} mt={4}>
      {toolCalls.map((tc, i) => (
        <ToolCallItem key={i} tc={tc} debugMode={debugMode} streaming={streaming} />
      ))}
    </Stack>
  );
}
