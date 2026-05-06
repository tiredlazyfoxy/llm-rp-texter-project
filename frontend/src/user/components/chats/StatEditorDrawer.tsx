import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Divider,
  Drawer,
  MultiSelect,
  NumberInput,
  Select,
  Stack,
  Text,
} from "@mantine/core";
import { observer } from "mobx-react-lite";
import {
  ChatPageState,
  closeStatDrawer,
  submitStatUpdates,
} from "../../pages/chatPageState";

interface StatEditorDrawerProps {
  state: ChatPageState;
}

type DraftValue = number | string | string[];

interface DraftEntry {
  value: DraftValue;
  /** Reset key — increments when the underlying snapshot changes so widgets re-mount. */
  generation: number;
}

type DraftMap = Record<string, DraftEntry>;

/** Owner derived from `StatDefinition.scope` (`character` -> `user`). */
function ownerFor(def: StatDefinition): "user" | "world" {
  return def.scope === "character" ? "user" : "world";
}

/** Stable key for a stat entry (`<owner>:<name>`). */
function keyFor(def: StatDefinition): string {
  return `${ownerFor(def)}:${def.name}`;
}

/** Pull the live value for a stat from the page snapshot, or fall back to default. */
function snapshotValue(
  def: StatDefinition,
  snap: ChatStateSnapshot | null,
): number | string | string[] {
  const bag =
    ownerFor(def) === "user"
      ? snap?.character_stats ?? {}
      : snap?.world_stats ?? {};
  const v = bag[def.name];
  if (v !== undefined) return v;
  // Fallback: derive a sensible default from the definition.
  if (def.stat_type === "int") {
    const parsed = Number(def.default_value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  if (def.stat_type === "set") {
    if (!def.default_value) return [];
    try {
      const parsed: unknown = JSON.parse(def.default_value);
      if (Array.isArray(parsed)) {
        return parsed.filter((x): x is string => typeof x === "string");
      }
    } catch {
      // fall through
    }
    return [];
  }
  return def.default_value ?? "";
}

function StatRowEditor({
  def,
  draft,
  onChange,
}: {
  def: StatDefinition;
  draft: DraftEntry;
  onChange: (next: DraftValue) => void;
}) {
  if (def.stat_type === "int") {
    const intValue =
      typeof draft.value === "number"
        ? draft.value
        : Number(draft.value);
    return (
      <NumberInput
        key={`int-${def.name}-${draft.generation}`}
        label={def.name}
        description={def.hidden ? "hidden" : undefined}
        value={Number.isFinite(intValue) ? intValue : 0}
        onChange={(v) => onChange(typeof v === "number" ? v : Number(v) || 0)}
        min={def.min_value ?? undefined}
        max={def.max_value ?? undefined}
        size="xs"
        allowDecimal={false}
      />
    );
  }

  if (def.stat_type === "enum") {
    const options = def.enum_values ?? [];
    const currentValue =
      typeof draft.value === "string" ? draft.value : String(draft.value);
    return (
      <Select
        key={`enum-${def.name}-${draft.generation}`}
        label={def.name}
        description={def.hidden ? "hidden" : undefined}
        data={options}
        value={options.includes(currentValue) ? currentValue : null}
        onChange={(v) => onChange(v ?? "")}
        clearable={false}
        size="xs"
      />
    );
  }

  if (def.stat_type === "set") {
    const options = def.enum_values ?? [];
    const arr = Array.isArray(draft.value)
      ? draft.value
      : typeof draft.value === "string" && draft.value.length > 0
        ? [draft.value]
        : [];
    return (
      <MultiSelect
        key={`set-${def.name}-${draft.generation}`}
        label={def.name}
        description={def.hidden ? "hidden" : undefined}
        data={options}
        value={arr.filter((v) => options.includes(v))}
        onChange={(v) => onChange(v)}
        size="xs"
      />
    );
  }

  return (
    <Text size="xs" c="dimmed">
      {def.name}: unsupported stat type "{def.stat_type}"
    </Text>
  );
}

export const StatEditorDrawer = observer(function StatEditorDrawer({
  state,
}: StatEditorDrawerProps) {
  const opened = state.statDrawerOpen;
  const submitting = state.statDrawerSubmitting;
  const error = state.statDrawerError;

  const statDefs = state.world?.stat_definitions ?? [];
  const snap = state.currentSnapshot;
  const charDefs = statDefs.filter((d) => d.scope === "character");
  const worldDefs = statDefs.filter((d) => d.scope === "world");

  const [drafts, setDrafts] = useState<DraftMap>({});

  // Re-seed drafts whenever the drawer opens or the underlying snapshot/defs change.
  useEffect(() => {
    if (!opened) return;
    const next: DraftMap = {};
    for (const def of statDefs) {
      const k = keyFor(def);
      const prev = drafts[k];
      next[k] = {
        value: snapshotValue(def, snap),
        generation: (prev?.generation ?? 0) + 1,
      };
    }
    setDrafts(next);
    // Intentionally exclude `drafts` to avoid an update loop — re-seeding
    // is bound to drawer-open + snapshot identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, snap, statDefs.length]);

  function setDraftValue(def: StatDefinition, value: DraftValue): void {
    const k = keyFor(def);
    setDrafts((cur) => ({
      ...cur,
      [k]: { value, generation: cur[k]?.generation ?? 0 },
    }));
  }

  function buildPayload(): StatUpdateItem[] {
    const out: StatUpdateItem[] = [];
    for (const def of statDefs) {
      const k = keyFor(def);
      const d = drafts[k];
      if (!d) continue;
      const original = snapshotValue(def, snap);
      if (valuesEqual(original, d.value, def.stat_type)) continue;
      out.push({
        owner: ownerFor(def),
        name: def.name,
        value: d.value,
      });
    }
    return out;
  }

  async function handleSave(): Promise<void> {
    const payload = buildPayload();
    if (payload.length === 0) {
      closeStatDrawer(state);
      return;
    }
    await submitStatUpdates(state, payload);
  }

  return (
    <Drawer
      opened={opened}
      onClose={() => closeStatDrawer(state)}
      title="Edit chat stats"
      position="right"
      size="sm"
    >
      <Stack gap="md">
        {error && (
          <Alert color="red" variant="light" title="Update failed">
            {error}
          </Alert>
        )}

        {statDefs.length === 0 && (
          <Text size="xs" c="dimmed">No stats defined for this world.</Text>
        )}

        {charDefs.length > 0 && (
          <>
            <Text size="sm" fw={600}>Character stats</Text>
            <Stack gap="xs">
              {charDefs.map((def) => {
                const k = keyFor(def);
                const d = drafts[k];
                if (!d) return null;
                return (
                  <StatRowEditor
                    key={k}
                    def={def}
                    draft={d}
                    onChange={(v) => setDraftValue(def, v)}
                  />
                );
              })}
            </Stack>
          </>
        )}

        {charDefs.length > 0 && worldDefs.length > 0 && <Divider />}

        {worldDefs.length > 0 && (
          <>
            <Text size="sm" fw={600}>World stats</Text>
            <Stack gap="xs">
              {worldDefs.map((def) => {
                const k = keyFor(def);
                const d = drafts[k];
                if (!d) return null;
                return (
                  <StatRowEditor
                    key={k}
                    def={def}
                    draft={d}
                    onChange={(v) => setDraftValue(def, v)}
                  />
                );
              })}
            </Stack>
          </>
        )}

        <Divider />
        <Button onClick={handleSave} loading={submitting}>
          Save
        </Button>
      </Stack>
    </Drawer>
  );
});

/** Compare two stat values for equality, normalizing per kind. */
function valuesEqual(
  a: number | string | string[],
  b: number | string | string[],
  kind: StatDefinition["stat_type"],
): boolean {
  if (kind === "int") {
    const an = typeof a === "number" ? a : Number(a);
    const bn = typeof b === "number" ? b : Number(b);
    return an === bn;
  }
  if (kind === "set") {
    const aa = Array.isArray(a) ? [...a].sort() : [];
    const bb = Array.isArray(b) ? [...b].sort() : [];
    if (aa.length !== bb.length) return false;
    return aa.every((v, i) => v === bb[i]);
  }
  return String(a) === String(b);
}
