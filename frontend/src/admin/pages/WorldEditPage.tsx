import { useEffect, useState } from "react";
import { makeAutoObservable } from "mobx";
import { observer } from "mobx-react-lite";
import { useNavigate } from "react-router-dom";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  Container,
  Group,
  Loader,
  Modal,
  NumberInput,
  Paper,
  Select,
  Stack,
  Table,
  TagsInput,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import {
  IconArrowLeft,
  IconArrowDown,
  IconArrowUp,
  IconCopy,
  IconEdit,
  IconPlus,
  IconSparkles,
  IconTrash,
} from "@tabler/icons-react";
import { getCurrentUser } from "../../auth";
import type { RuleItem, StatDefinitionItem } from "../../types/world";
import {
  createRule,
  createStat,
  deleteRule,
  deleteStat,
  updateRule,
  updateStat,
} from "../../api/worlds";
import {
  WorldEditPageState,
  loadWorldEdit,
  saveWorld,
  cloneWorld,
  deleteWorld,
  refreshStatsAndRules,
  reorderRules,
} from "./worldEditPageState";

// ---------------------------------------------------------------------------
// Stat form modal
// ---------------------------------------------------------------------------

interface StatFormModalProps {
  opened: boolean;
  stat: StatDefinitionItem | null;
  worldId: string;
  onClose: () => void;
  onSaved: () => void;
}

type AsyncStatus = "idle" | "loading" | "ready" | "error";

class StatDraft {
  name = "";
  description = "";
  scope = "character";
  statType = "int";
  defaultValue = "0";
  minValue: number | string = "";
  maxValue: number | string = "";
  enumValues: string[] = [];
  hidden = false;

  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  loadFrom(stat: StatDefinitionItem | null): void {
    if (stat) {
      this.name = stat.name;
      this.description = stat.description;
      this.scope = stat.scope;
      this.statType = stat.stat_type;
      this.defaultValue = stat.default_value;
      this.minValue = stat.min_value ?? "";
      this.maxValue = stat.max_value ?? "";
      this.enumValues = stat.enum_values ?? [];
      this.hidden = stat.hidden ?? false;
    } else {
      this.name = "";
      this.description = "";
      this.scope = "character";
      this.statType = "int";
      this.defaultValue = "0";
      this.minValue = "";
      this.maxValue = "";
      this.enumValues = [];
      this.hidden = false;
    }
    this.saveStatus = "idle";
    this.saveError = null;
  }

  get nameError(): string | null {
    return !this.name.trim() ? "Name is required" : null;
  }

  get canSubmit(): boolean {
    return this.nameError === null && this.saveStatus !== "loading";
  }
}

const StatFormModal = observer(function StatFormModal({
  opened,
  stat,
  worldId,
  onClose,
  onSaved,
}: StatFormModalProps) {
  const isEdit = stat !== null;
  const [draft] = useState(() => new StatDraft());

  useEffect(() => {
    if (opened) draft.loadFrom(stat);
  }, [opened, stat, draft]);

  const handleSubmit = async () => {
    if (!draft.canSubmit) return;
    draft.saveStatus = "loading";
    draft.saveError = null;
    try {
      const data = {
        name: draft.name.trim(),
        description: draft.description,
        scope: draft.scope,
        stat_type: draft.statType,
        default_value: draft.defaultValue,
        min_value: draft.statType === "int" && draft.minValue !== "" ? Number(draft.minValue) : undefined,
        max_value: draft.statType === "int" && draft.maxValue !== "" ? Number(draft.maxValue) : undefined,
        enum_values: (draft.statType === "enum" || draft.statType === "set") && draft.enumValues.length > 0 ? draft.enumValues : undefined,
        hidden: draft.hidden,
      };
      if (isEdit) {
        await updateStat(worldId, stat.id, data);
      } else {
        await createStat(worldId, data);
      }
      draft.saveStatus = "ready";
      onSaved();
      onClose();
    } catch (e) {
      draft.saveStatus = "error";
      draft.saveError = e instanceof Error ? e.message : "Failed to save stat";
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={isEdit ? "Edit Stat" : "Create Stat"}>
      <Stack>
        {draft.saveError && <Alert color="red">{draft.saveError}</Alert>}
        <TextInput
          label="Name"
          value={draft.name}
          onChange={e => { draft.name = e.currentTarget.value; }}
          error={draft.nameError}
          required
        />
        <Textarea
          label="Description"
          value={draft.description}
          onChange={e => { draft.description = e.currentTarget.value; }}
          minRows={2}
        />
        <Select
          label="Scope"
          data={[{ value: "character", label: "Character" }, { value: "world", label: "World" }]}
          value={draft.scope}
          onChange={v => { draft.scope = v || "character"; }}
        />
        <Select
          label="Type"
          data={[
            { value: "int", label: "Integer" },
            { value: "enum", label: "Enum (single)" },
            { value: "set", label: "Set (multiple)" },
          ]}
          value={draft.statType}
          onChange={v => { draft.statType = v || "int"; }}
        />
        <TextInput
          label="Default Value"
          value={draft.defaultValue}
          onChange={e => { draft.defaultValue = e.currentTarget.value; }}
        />
        {draft.statType === "int" && (
          <Group grow>
            <NumberInput label="Min" value={draft.minValue} onChange={v => { draft.minValue = v; }} />
            <NumberInput label="Max" value={draft.maxValue} onChange={v => { draft.maxValue = v; }} />
          </Group>
        )}
        {(draft.statType === "enum" || draft.statType === "set") && (
          <TagsInput
            label="Values"
            value={draft.enumValues}
            onChange={v => { draft.enumValues = v; }}
            placeholder="Type and press Enter"
          />
        )}
        <Checkbox
          label="Hidden from players"
          checked={draft.hidden}
          onChange={e => { draft.hidden = e.currentTarget.checked; }}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            disabled={!draft.canSubmit}
            loading={draft.saveStatus === "loading"}
          >
            {isEdit ? "Save" : "Create"}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
});

// ---------------------------------------------------------------------------
// Rule form modal
// ---------------------------------------------------------------------------

interface RuleFormModalProps {
  opened: boolean;
  rule: RuleItem | null;
  worldId: string;
  onClose: () => void;
  onSaved: () => void;
}

class RuleDraft {
  ruleText = "";
  saveStatus: AsyncStatus = "idle";
  saveError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  loadFrom(rule: RuleItem | null): void {
    this.ruleText = rule?.rule_text ?? "";
    this.saveStatus = "idle";
    this.saveError = null;
  }

  get textError(): string | null {
    return !this.ruleText.trim() ? "Rule text is required" : null;
  }

  get canSubmit(): boolean {
    return this.textError === null && this.saveStatus !== "loading";
  }
}

const RuleFormModal = observer(function RuleFormModal({
  opened,
  rule,
  worldId,
  onClose,
  onSaved,
}: RuleFormModalProps) {
  const isEdit = rule !== null;
  const [draft] = useState(() => new RuleDraft());

  useEffect(() => {
    if (opened) draft.loadFrom(rule);
  }, [opened, rule, draft]);

  const handleSubmit = async () => {
    if (!draft.canSubmit) return;
    draft.saveStatus = "loading";
    draft.saveError = null;
    try {
      if (isEdit) {
        await updateRule(worldId, rule.id, { rule_text: draft.ruleText.trim() });
      } else {
        await createRule(worldId, { rule_text: draft.ruleText.trim() });
      }
      draft.saveStatus = "ready";
      onSaved();
      onClose();
    } catch (e) {
      draft.saveStatus = "error";
      draft.saveError = e instanceof Error ? e.message : "Failed to save rule";
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={isEdit ? "Edit Rule" : "Add Rule"}>
      <Stack>
        {draft.saveError && <Alert color="red">{draft.saveError}</Alert>}
        <Textarea
          label="Rule Text"
          value={draft.ruleText}
          onChange={e => { draft.ruleText = e.currentTarget.value; }}
          error={draft.textError}
          minRows={3}
          required
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            disabled={!draft.canSubmit}
            loading={draft.saveStatus === "loading"}
          >
            {isEdit ? "Save" : "Add"}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
});

// ---------------------------------------------------------------------------
// Resizable textarea height storage (localStorage)
// ---------------------------------------------------------------------------

const LS_HEIGHT = "llmrp_world_editor_height_";
const DEFAULT_HEIGHTS: Record<string, number> = {
  description: 100,
  character_template: 240,
  initial_message: 160,
};

function loadHeights(): Record<string, number> {
  const h: Record<string, number> = {};
  for (const [k, def] of Object.entries(DEFAULT_HEIGHTS)) {
    const stored = localStorage.getItem(LS_HEIGHT + k);
    h[k] = stored ? parseInt(stored) : def;
  }
  return h;
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

interface WorldEditPageProps {
  worldId: string;
}

export const WorldEditPage = observer(function WorldEditPage({ worldId }: WorldEditPageProps) {
  const [state] = useState(() => new WorldEditPageState(worldId));
  const [heights, setHeights] = useState<Record<string, number>>(() => loadHeights());
  const navigate = useNavigate();

  const [statModalOpen, setStatModalOpen] = useState(false);
  const [editStat, setEditStat] = useState<StatDefinitionItem | null>(null);
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [editRule, setEditRule] = useState<RuleItem | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    loadWorldEdit(state, ctrl.signal);
    return () => ctrl.abort();
  }, []);

  const onResized = (field: string) => (e: React.MouseEvent<HTMLTextAreaElement>) => {
    const px = e.currentTarget.offsetHeight;
    setHeights(prev => ({ ...prev, [field]: px }));
    localStorage.setItem(LS_HEIGHT + field, String(px));
  };
  const resizable = (field: string) => ({
    styles: { input: { height: heights[field], resize: "vertical" as const, overflow: "auto" } },
    onMouseUp: onResized(field),
  });

  const handleSave = async () => {
    if (!state.canSubmit) return;
    const ctrl = new AbortController();
    await saveWorld(state, ctrl.signal);
    if (state.saveSuccess) {
      setTimeout(() => {
        if (state.saveSuccess) state.saveSuccess = null;
      }, 3000);
    }
  };

  const handleClone = async () => {
    const ctrl = new AbortController();
    const newId = await cloneWorld(state, ctrl.signal);
    if (newId) navigate(`/worlds/${newId}`);
  };

  const handleDeleteWorld = async () => {
    const ctrl = new AbortController();
    const ok = await deleteWorld(state, ctrl.signal);
    if (ok) {
      navigate("/worlds");
    } else {
      setDeleteModalOpen(false);
    }
  };

  const handleDeleteStat = async (stat: StatDefinitionItem) => {
    if (!window.confirm(`Delete stat "${stat.name}"?`)) return;
    try {
      await deleteStat(worldId, stat.id);
      const ctrl = new AbortController();
      await refreshStatsAndRules(state, ctrl.signal);
    } catch (e) {
      state.saveError = e instanceof Error ? e.message : "Failed to delete stat";
    }
  };

  const handleDeleteRule = async (rule: RuleItem) => {
    if (!window.confirm("Delete this rule?")) return;
    try {
      await deleteRule(worldId, rule.id);
      const ctrl = new AbortController();
      await refreshStatsAndRules(state, ctrl.signal);
    } catch (e) {
      state.saveError = e instanceof Error ? e.message : "Failed to delete rule";
    }
  };

  const handleMoveRule = async (index: number, direction: "up" | "down") => {
    const newRules = [...state.rules];
    const swapIdx = direction === "up" ? index - 1 : index + 1;
    if (swapIdx < 0 || swapIdx >= newRules.length) return;
    [newRules[index], newRules[swapIdx]] = [newRules[swapIdx], newRules[index]];
    const ctrl = new AbortController();
    await reorderRules(state, newRules.map(r => r.id), ctrl.signal);
  };

  const refreshOnSubmodalSaved = () => {
    const ctrl = new AbortController();
    void refreshStatsAndRules(state, ctrl.signal);
  };

  const currentUser = getCurrentUser();
  const isAdmin = currentUser?.role === "admin";

  if (state.worldStatus === "loading" || state.worldStatus === "idle") {
    return <Container py="md"><Group justify="center" py="xl"><Loader /></Group></Container>;
  }
  if (state.worldStatus === "error") {
    return <Container py="md"><Alert color="red">{state.worldError}</Alert></Container>;
  }
  if (!state.world) return null;

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Group>
          <Button
            variant="subtle"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => navigate(`/worlds/${worldId}`)}
          >
            Back
          </Button>
          <Title order={3}>{state.world.name || "Edit World"}</Title>
        </Group>
        <Group>
          <Button
            variant="default"
            leftSection={<IconCopy size={16} />}
            onClick={handleClone}
            loading={state.cloneStatus === "loading"}
          >
            Clone
          </Button>
          {isAdmin && (
            <Button
              variant="light"
              color="red"
              leftSection={<IconTrash size={16} />}
              onClick={() => { setDeleteConfirmed(false); setDeleteModalOpen(true); }}
            >
              Delete
            </Button>
          )}
          <Button
            onClick={handleSave}
            disabled={!state.canSubmit}
            loading={state.saveStatus === "loading"}
          >
            Save
          </Button>
        </Group>
      </Group>

      {state.saveError && (
        <Alert color="red" mb="md" withCloseButton onClose={() => { state.saveError = null; }}>
          {state.saveError}
        </Alert>
      )}
      {state.saveSuccess && (
        <Alert color="green" mb="md" withCloseButton onClose={() => { state.saveSuccess = null; }}>
          {state.saveSuccess}
        </Alert>
      )}

      {/* Main fields */}
      <Paper p="md" mb="md" withBorder>
        <Stack>
          <Group grow>
            <TextInput
              label="Name"
              value={state.draft.name}
              onChange={e => {
                state.draft.name = e.currentTarget.value;
                if (state.serverErrors.name) delete state.serverErrors.name;
              }}
              error={state.errors.name}
            />
            <Select
              label="Status"
              data={[
                { value: "draft", label: "Draft" },
                { value: "public", label: "Public" },
                { value: "private", label: "Private" },
                { value: "archived", label: "Archived" },
              ]}
              value={state.draft.status}
              onChange={v => { state.draft.status = v || "draft"; }}
            />
          </Group>
          <Textarea
            label={
              <Group gap={4} wrap="nowrap">
                Description
                <ActionIcon
                  variant="subtle"
                  size="xs"
                  title="Edit with AI"
                  onClick={() => navigate(`/worlds/${worldId}/field/description`)}
                >
                  <IconSparkles size={12} />
                </ActionIcon>
              </Group>
            }
            value={state.draft.description}
            onChange={e => { state.draft.description = e.currentTarget.value; }}
            {...resizable("description")}
          />
          <Textarea
            label="Character Template"
            value={state.draft.character_template}
            onChange={e => { state.draft.character_template = e.currentTarget.value; }}
            placeholder="Use {PLACEHOLDER} tokens"
            {...resizable("character_template")}
          />
          <Textarea
            label={
              <Group gap={4} wrap="nowrap">
                Initial Message
                <ActionIcon
                  variant="subtle"
                  size="xs"
                  title="Edit with AI"
                  onClick={() => navigate(`/worlds/${worldId}/field/initial_message`)}
                >
                  <IconSparkles size={12} />
                </ActionIcon>
              </Group>
            }
            value={state.draft.initial_message}
            onChange={e => { state.draft.initial_message = e.currentTarget.value; }}
            placeholder="Supports {character_name}, {location_name}, {location_summary}"
            {...resizable("initial_message")}
          />
        </Stack>
      </Paper>

      {/* Pipeline picker */}
      <Paper p="md" mb="md" withBorder>
        <Stack>
          <Select
            label="Pipeline"
            description="Pipelines define the generation flow (simple / chain / agentic)."
            data={state.pipelines.map(p => ({ value: p.id, label: `${p.name} (${p.kind})` }))}
            value={state.draft.pipeline_id}
            onChange={v => { state.draft.pipeline_id = v; }}
            searchable
            clearable
          />
          {state.draft.pipeline_id && (
            <Button
              variant="subtle"
              onClick={() => navigate(`/pipelines/${state.draft.pipeline_id}`)}
            >
              Edit pipeline
            </Button>
          )}
        </Stack>
      </Paper>

      {/* Stats section */}
      <Paper p="md" mb="md" withBorder>
        <Group justify="space-between" mb="sm">
          <Title order={5}>Stat Definitions</Title>
          <Button
            size="compact-sm"
            leftSection={<IconPlus size={14} />}
            onClick={() => { setEditStat(null); setStatModalOpen(true); }}
          >
            Add Stat
          </Button>
        </Group>
        {state.stats.length === 0 ? (
          <Text c="dimmed" size="sm">No stats defined.</Text>
        ) : (
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Scope</Table.Th>
                <Table.Th>Type</Table.Th>
                <Table.Th>Default</Table.Th>
                <Table.Th w={80} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {state.stats.map(stat => (
                <Table.Tr key={stat.id}>
                  <Table.Td>
                    <Text size="sm" fw={500}>{stat.name}</Text>
                    {stat.description && <Text size="xs" c="dimmed" lineClamp={1}>{stat.description}</Text>}
                  </Table.Td>
                  <Table.Td><Badge size="sm" variant="light">{stat.scope}</Badge></Table.Td>
                  <Table.Td><Badge size="sm" variant="outline">{stat.stat_type}</Badge></Table.Td>
                  <Table.Td><Text size="sm">{stat.default_value}</Text></Table.Td>
                  <Table.Td>
                    <Group gap={4}>
                      <ActionIcon variant="subtle" size="sm" onClick={() => { setEditStat(stat); setStatModalOpen(true); }}>
                        <IconEdit size={14} />
                      </ActionIcon>
                      <ActionIcon variant="subtle" size="sm" color="red" onClick={() => handleDeleteStat(stat)}>
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      {/* Rules section */}
      <Paper p="md" mb="md" withBorder>
        <Group justify="space-between" mb="sm">
          <Title order={5}>Rules</Title>
          <Button
            size="compact-sm"
            leftSection={<IconPlus size={14} />}
            onClick={() => { setEditRule(null); setRuleModalOpen(true); }}
          >
            Add Rule
          </Button>
        </Group>
        {state.rules.length === 0 ? (
          <Text c="dimmed" size="sm">No rules defined.</Text>
        ) : (
          <Stack gap="xs">
            {state.rules.map((rule, idx) => (
              <Paper key={rule.id} p="xs" withBorder>
                <Group justify="space-between" wrap="nowrap">
                  <Group gap="xs" wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
                    <Badge size="sm" variant="light" circle>{idx + 1}</Badge>
                    <Text size="sm" style={{ flex: 1, minWidth: 0 }} lineClamp={2}>{rule.rule_text}</Text>
                  </Group>
                  <Group gap={4} wrap="nowrap">
                    <ActionIcon variant="subtle" size="sm" disabled={idx === 0} onClick={() => handleMoveRule(idx, "up")}>
                      <IconArrowUp size={14} />
                    </ActionIcon>
                    <ActionIcon variant="subtle" size="sm" disabled={idx === state.rules.length - 1} onClick={() => handleMoveRule(idx, "down")}>
                      <IconArrowDown size={14} />
                    </ActionIcon>
                    <ActionIcon variant="subtle" size="sm" onClick={() => { setEditRule(rule); setRuleModalOpen(true); }}>
                      <IconEdit size={14} />
                    </ActionIcon>
                    <ActionIcon variant="subtle" size="sm" color="red" onClick={() => handleDeleteRule(rule)}>
                      <IconTrash size={14} />
                    </ActionIcon>
                  </Group>
                </Group>
              </Paper>
            ))}
          </Stack>
        )}
      </Paper>

      {/* Modals */}
      <StatFormModal
        opened={statModalOpen}
        stat={editStat}
        worldId={worldId}
        onClose={() => setStatModalOpen(false)}
        onSaved={refreshOnSubmodalSaved}
      />
      <RuleFormModal
        opened={ruleModalOpen}
        rule={editRule}
        worldId={worldId}
        onClose={() => setRuleModalOpen(false)}
        onSaved={refreshOnSubmodalSaved}
      />
      <Modal opened={deleteModalOpen} onClose={() => setDeleteModalOpen(false)} title="Delete World">
        <Stack>
          <Text>This will permanently remove <Text span fw={700}>{state.world.name}</Text> and all its documents, stats, rules, and vector data.</Text>
          <Checkbox
            label="I understand this action cannot be undone"
            checked={deleteConfirmed}
            onChange={e => setDeleteConfirmed(e.currentTarget.checked)}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleteModalOpen(false)}>Cancel</Button>
            <Button
              color="red"
              disabled={!deleteConfirmed}
              loading={state.deleteStatus === "loading"}
              onClick={handleDeleteWorld}
            >
              Delete World
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  );
});
