import { useState } from "react";
import { Badge, Collapse, Group, Loader, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";

const PLANNING_TOOLS = new Set(["add_fact", "add_decision", "update_stat"]);

interface ToolCallTraceProps {
  toolCalls: ToolCallInfo[];
  debugMode?: boolean;
  streaming?: boolean;
  /** Start groups collapsed (for completed messages) */
  defaultCollapsed?: boolean;
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

function ToolCallGroup({
  label,
  toolCalls,
  debugMode,
  streaming,
  defaultOpen,
  count,
}: {
  label: string;
  toolCalls: ToolCallInfo[];
  debugMode?: boolean;
  streaming?: boolean;
  defaultOpen: boolean;
  count?: number;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (toolCalls.length === 0) return null;

  return (
    <div>
      <UnstyledButton onClick={() => setOpen((o) => !o)}>
        <Group gap={4}>
          {open ? <IconChevronDown size={12} /> : <IconChevronRight size={12} />}
          <Text size="xs" c="dimmed" fw={600}>{label}</Text>
          {count !== undefined && (
            <Badge size="xs" variant="light" color="gray">{count}</Badge>
          )}
        </Group>
      </UnstyledButton>
      <Collapse in={open}>
        <Stack gap={2} mt={2} pl="xs">
          {toolCalls.map((tc, i) => (
            <ToolCallItem key={i} tc={tc} debugMode={debugMode} streaming={streaming} />
          ))}
        </Stack>
      </Collapse>
    </div>
  );
}

/** Group tool calls by stage_name, preserving insertion order. */
function groupByStage(toolCalls: ToolCallInfo[]): Array<{ stage: string; calls: ToolCallInfo[] }> {
  const groups: Array<{ stage: string; calls: ToolCallInfo[] }> = [];
  for (const tc of toolCalls) {
    const stage = tc.stage_name || "";
    const last = groups[groups.length - 1];
    if (last && last.stage === stage) {
      last.calls.push(tc);
    } else {
      groups.push({ stage, calls: [tc] });
    }
  }
  return groups;
}

/** Legacy grouping by tool category (for old messages without stage_name). */
function groupByCategory(toolCalls: ToolCallInfo[]): Array<{ stage: string; calls: ToolCallInfo[] }> {
  const research = toolCalls.filter((tc) => !PLANNING_TOOLS.has(tc.tool_name));
  const planning = toolCalls.filter((tc) => PLANNING_TOOLS.has(tc.tool_name));
  const groups: Array<{ stage: string; calls: ToolCallInfo[] }> = [];
  if (research.length > 0) groups.push({ stage: "Research", calls: research });
  if (planning.length > 0) groups.push({ stage: "Planning", calls: planning });
  return groups;
}

export function ToolCallTrace({ toolCalls, debugMode, streaming, defaultCollapsed }: ToolCallTraceProps) {
  if (toolCalls.length === 0) return null;

  // Completed messages: collapsible flat list
  if (!streaming) {
    return (
      <ToolCallGroup
        label={`Tool calls (${toolCalls.length})`}
        toolCalls={toolCalls}
        debugMode={debugMode}
        defaultOpen={!defaultCollapsed}
        count={undefined}
      />
    );
  }

  // Streaming: group by stage for live debug visibility
  const hasStageNames = toolCalls.some((tc) => tc.stage_name);
  const groups = hasStageNames ? groupByStage(toolCalls) : groupByCategory(toolCalls);

  if (groups.length <= 1) {
    return (
      <Stack gap={2} mt={4}>
        {toolCalls.map((tc, i) => (
          <ToolCallItem key={i} tc={tc} debugMode={debugMode} streaming />
        ))}
      </Stack>
    );
  }

  return (
    <Stack gap={4} mt={4}>
      {groups.map((g, i) => (
        <ToolCallGroup
          key={`${g.stage}-${i}`}
          label={g.stage || `Step ${i + 1}`}
          toolCalls={g.calls}
          debugMode={debugMode}
          streaming
          defaultOpen={!defaultCollapsed}
          count={g.calls.length}
        />
      ))}
    </Stack>
  );
}
