import { useCallback, useEffect, useState } from "react";
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
import type { RuleItem, StatDefinitionItem, WorldDetail } from "../../types/world";
import {
  cloneWorld,
  createRule,
  createStat,
  deleteRule,
  deleteStat,
  deleteWorld,
  getWorld,
  reorderRules,
  updateRule,
  updateStat,
  updateWorld,
} from "../../api/worlds";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractWorldId(): string | null {
  const m = window.location.pathname.match(/\/admin\/worlds\/(\d+)\/edit/);
  return m ? m[1] : null;
}

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

function StatFormModal({ opened, stat, worldId, onClose, onSaved }: StatFormModalProps) {
  const isEdit = stat !== null;
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [scope, setScope] = useState("character");
  const [statType, setStatType] = useState("int");
  const [defaultValue, setDefaultValue] = useState("0");
  const [minValue, setMinValue] = useState<number | string>("");
  const [maxValue, setMaxValue] = useState<number | string>("");
  const [enumValues, setEnumValues] = useState<string[]>([]);
  const [hidden, setHidden] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (opened && stat) {
      setName(stat.name);
      setDescription(stat.description);
      setScope(stat.scope);
      setStatType(stat.stat_type);
      setDefaultValue(stat.default_value);
      setMinValue(stat.min_value ?? "");
      setMaxValue(stat.max_value ?? "");
      setEnumValues(stat.enum_values ?? []);
      setHidden(stat.hidden ?? false);
    } else if (opened) {
      setName("");
      setDescription("");
      setScope("character");
      setStatType("int");
      setDefaultValue("0");
      setMinValue("");
      setMaxValue("");
      setEnumValues([]);
      setHidden(false);
    }
    setError(null);
  }, [opened, stat]);

  const handleSubmit = async () => {
    if (!name.trim()) { setError("Name is required"); return; }
    setLoading(true);
    setError(null);
    try {
      const data = {
        name: name.trim(),
        description,
        scope,
        stat_type: statType,
        default_value: defaultValue,
        min_value: statType === "int" && minValue !== "" ? Number(minValue) : undefined,
        max_value: statType === "int" && maxValue !== "" ? Number(maxValue) : undefined,
        enum_values: (statType === "enum" || statType === "set") && enumValues.length > 0 ? enumValues : undefined,
        hidden,
      };
      if (isEdit) {
        await updateStat(worldId, stat.id, data);
      } else {
        await createStat(worldId, data);
      }
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save stat");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={isEdit ? "Edit Stat" : "Create Stat"}>
      <Stack>
        {error && <Alert color="red">{error}</Alert>}
        <TextInput label="Name" value={name} onChange={e => setName(e.currentTarget.value)} required />
        <Textarea label="Description" value={description} onChange={e => setDescription(e.currentTarget.value)} minRows={2} />
        <Select
          label="Scope"
          data={[{ value: "character", label: "Character" }, { value: "world", label: "World" }]}
          value={scope}
          onChange={v => setScope(v || "character")}
        />
        <Select
          label="Type"
          data={[
            { value: "int", label: "Integer" },
            { value: "enum", label: "Enum (single)" },
            { value: "set", label: "Set (multiple)" },
          ]}
          value={statType}
          onChange={v => setStatType(v || "int")}
        />
        <TextInput label="Default Value" value={defaultValue} onChange={e => setDefaultValue(e.currentTarget.value)} />
        {statType === "int" && (
          <Group grow>
            <NumberInput label="Min" value={minValue} onChange={setMinValue} />
            <NumberInput label="Max" value={maxValue} onChange={setMaxValue} />
          </Group>
        )}
        {(statType === "enum" || statType === "set") && (
          <TagsInput label="Values" value={enumValues} onChange={setEnumValues} placeholder="Type and press Enter" />
        )}
        <Checkbox label="Hidden from players" checked={hidden} onChange={e => setHidden(e.currentTarget.checked)} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} loading={loading}>{isEdit ? "Save" : "Create"}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

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

function RuleFormModal({ opened, rule, worldId, onClose, onSaved }: RuleFormModalProps) {
  const isEdit = rule !== null;
  const [ruleText, setRuleText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (opened && rule) {
      setRuleText(rule.rule_text);
    } else if (opened) {
      setRuleText("");
    }
    setError(null);
  }, [opened, rule]);

  const handleSubmit = async () => {
    if (!ruleText.trim()) { setError("Rule text is required"); return; }
    setLoading(true);
    setError(null);
    try {
      if (isEdit) {
        await updateRule(worldId, rule.id, { rule_text: ruleText.trim() });
      } else {
        await createRule(worldId, { rule_text: ruleText.trim() });
      }
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save rule");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={isEdit ? "Edit Rule" : "Add Rule"}>
      <Stack>
        {error && <Alert color="red">{error}</Alert>}
        <Textarea label="Rule Text" value={ruleText} onChange={e => setRuleText(e.currentTarget.value)} minRows={3} required />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} loading={loading}>{isEdit ? "Save" : "Add"}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function WorldEditPage() {
  const worldId = extractWorldId();
  const [world, setWorld] = useState<WorldDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [lore, setLore] = useState("");
  const [characterTemplate, setCharacterTemplate] = useState("");
  const [initialMessage, setInitialMessage] = useState("");
  const [pipelineId, setPipelineId] = useState<string | null>(null);
  const [worldStatus, setWorldStatus] = useState("draft");

  // Resizable textarea heights (persisted to localStorage)
  const LS_HEIGHT = "llmrp_world_editor_height_";
  const DEFAULT_HEIGHTS: Record<string, number> = {
    description: 100, system_prompt: 240, character_template: 240,
    initial_message: 160,
  };
  const [heights, setHeights] = useState<Record<string, number>>(() => {
    const h: Record<string, number> = {};
    for (const [k, def] of Object.entries(DEFAULT_HEIGHTS)) {
      const stored = localStorage.getItem(LS_HEIGHT + k);
      h[k] = stored ? parseInt(stored) : def;
    }
    return h;
  });
  const onResized = (field: string) => (e: React.MouseEvent<HTMLTextAreaElement>) => {
    const px = e.currentTarget.offsetHeight;
    setHeights(prev => ({ ...prev, [field]: px }));
    localStorage.setItem(LS_HEIGHT + field, String(px));
  };
  const resizable = (field: string) => ({
    styles: { input: { height: heights[field], resize: "vertical" as const, overflow: "auto" } },
    onMouseUp: onResized(field),
  });

  // Stats & rules
  const [stats, setStats] = useState<StatDefinitionItem[]>([]);
  const [rules, setRules] = useState<RuleItem[]>([]);
  const [statModalOpen, setStatModalOpen] = useState(false);
  const [editStat, setEditStat] = useState<StatDefinitionItem | null>(null);
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [editRule, setEditRule] = useState<RuleItem | null>(null);

  const loadWorld = useCallback(async () => {
    if (!worldId) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await getWorld(worldId);
      setWorld(detail);
      setName(detail.name);
      setDescription(detail.description);
      setLore(detail.lore);
      setCharacterTemplate(detail.character_template);
      setInitialMessage(detail.initial_message);
      setPipelineId(detail.pipeline_id);
      setWorldStatus(detail.status);
      setStats(detail.stats);
      setRules(detail.rules);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load world");
    } finally {
      setLoading(false);
    }
  }, [worldId]);

  useEffect(() => {
    loadWorld();
  }, [loadWorld]);

  const handleSave = async () => {
    if (!worldId) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await updateWorld(worldId, {
        name, description, lore,
        character_template: characterTemplate,
        initial_message: initialMessage,
        pipeline_id: pipelineId,
        status: worldStatus,
      });
      setSuccess("World saved");
      setTimeout(() => setSuccess(null), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save world");
    } finally {
      setSaving(false);
    }
  };

  const refreshStatsRules = useCallback(async () => {
    if (!worldId) return;
    const detail = await getWorld(worldId);
    setStats(detail.stats);
    setRules(detail.rules);
  }, [worldId]);

  const handleDeleteStat = async (stat: StatDefinitionItem) => {
    if (!worldId) return;
    if (!window.confirm(`Delete stat "${stat.name}"?`)) return;
    try {
      await deleteStat(worldId, stat.id);
      await refreshStatsRules();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete stat");
    }
  };

  const handleDeleteRule = async (rule: RuleItem) => {
    if (!worldId) return;
    if (!window.confirm("Delete this rule?")) return;
    try {
      await deleteRule(worldId, rule.id);
      await refreshStatsRules();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete rule");
    }
  };

  const handleMoveRule = async (index: number, direction: "up" | "down") => {
    if (!worldId) return;
    const newRules = [...rules];
    const swapIdx = direction === "up" ? index - 1 : index + 1;
    if (swapIdx < 0 || swapIdx >= newRules.length) return;
    [newRules[index], newRules[swapIdx]] = [newRules[swapIdx], newRules[index]];
    try {
      const updated = await reorderRules(worldId, newRules.map(r => r.id));
      setRules(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to reorder rules");
    }
  };

  const currentUser = getCurrentUser();
  const isAdmin = currentUser?.role === "admin";

  const handleClone = async () => {
    if (!worldId) return;
    try {
      const cloned = await cloneWorld(worldId);
      window.location.href = `/admin/worlds/${cloned.id}`;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to clone world");
    }
  };

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDeleteWorld = async () => {
    if (!worldId) return;
    setDeleting(true);
    try {
      await deleteWorld(worldId);
      window.location.href = "/admin/worlds";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete world");
      setDeleteModalOpen(false);
    } finally {
      setDeleting(false);
    }
  };

  if (!worldId) return <Container py="md"><Alert color="red">Invalid world ID</Alert></Container>;

  if (loading) return <Container py="md"><Group justify="center" py="xl"><Loader /></Group></Container>;

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Group>
          <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => { window.location.href = `/admin/worlds/${worldId}`; }}>
            Back
          </Button>
          <Title order={3}>{world?.name || "Edit World"}</Title>
        </Group>
        <Group>
          <Button variant="default" leftSection={<IconCopy size={16} />} onClick={handleClone}>Clone</Button>
          {isAdmin && (
            <Button variant="light" color="red" leftSection={<IconTrash size={16} />} onClick={() => { setDeleteConfirmed(false); setDeleteModalOpen(true); }}>Delete</Button>
          )}
          <Button onClick={handleSave} loading={saving}>Save</Button>
        </Group>
      </Group>

      {error && <Alert color="red" mb="md" withCloseButton onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert color="green" mb="md" withCloseButton onClose={() => setSuccess(null)}>{success}</Alert>}

      {/* Main fields */}
      <Paper p="md" mb="md" withBorder>
        <Stack>
          <Group grow>
            <TextInput label="Name" value={name} onChange={e => setName(e.currentTarget.value)} />
            <Select
              label="Status"
              data={[
                { value: "draft", label: "Draft" },
                { value: "public", label: "Public" },
                { value: "private", label: "Private" },
                { value: "archived", label: "Archived" },
              ]}
              value={worldStatus}
              onChange={v => setWorldStatus(v || "draft")}
            />
          </Group>
          <Textarea
            label={<Group gap={4} wrap="nowrap">Description<ActionIcon variant="subtle" size="xs" title="Edit with AI" onClick={() => window.location.href = `/admin/worlds/${worldId}/field/description`}><IconSparkles size={12} /></ActionIcon></Group>}
            value={description} onChange={e => setDescription(e.currentTarget.value)}
            {...resizable("description")}
          />
          <Textarea label="Character Template" value={characterTemplate} onChange={e => setCharacterTemplate(e.currentTarget.value)} placeholder="Use {PLACEHOLDER} tokens" {...resizable("character_template")} />
          <Textarea
            label={<Group gap={4} wrap="nowrap">Initial Message<ActionIcon variant="subtle" size="xs" title="Edit with AI" onClick={() => window.location.href = `/admin/worlds/${worldId}/field/initial_message`}><IconSparkles size={12} /></ActionIcon></Group>}
            value={initialMessage} onChange={e => setInitialMessage(e.currentTarget.value)} placeholder="Supports {character_name}, {location_name}, {location_summary}"
            {...resizable("initial_message")}
          />
        </Stack>
      </Paper>

      {/* Pipeline picker — full UI lands in step 002 */}
      <Paper p="md" mb="md" withBorder>
        <Stack>
          <Text c="dimmed" size="sm">
            Pipeline picker — see step 002. Selected pipeline_id: {pipelineId ?? "(none)"}
          </Text>
        </Stack>
      </Paper>


      {/* Stats section */}
      <Paper p="md" mb="md" withBorder>
        <Group justify="space-between" mb="sm">
          <Title order={5}>Stat Definitions</Title>
          <Button size="compact-sm" leftSection={<IconPlus size={14} />} onClick={() => { setEditStat(null); setStatModalOpen(true); }}>
            Add Stat
          </Button>
        </Group>
        {stats.length === 0 ? (
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
              {stats.map(stat => (
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
          <Button size="compact-sm" leftSection={<IconPlus size={14} />} onClick={() => { setEditRule(null); setRuleModalOpen(true); }}>
            Add Rule
          </Button>
        </Group>
        {rules.length === 0 ? (
          <Text c="dimmed" size="sm">No rules defined.</Text>
        ) : (
          <Stack gap="xs">
            {rules.map((rule, idx) => (
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
                    <ActionIcon variant="subtle" size="sm" disabled={idx === rules.length - 1} onClick={() => handleMoveRule(idx, "down")}>
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
      {worldId && (
        <>
          <StatFormModal
            opened={statModalOpen}
            stat={editStat}
            worldId={worldId}
            onClose={() => setStatModalOpen(false)}
            onSaved={refreshStatsRules}
          />
          <RuleFormModal
            opened={ruleModalOpen}
            rule={editRule}
            worldId={worldId}
            onClose={() => setRuleModalOpen(false)}
            onSaved={refreshStatsRules}
          />
          <Modal opened={deleteModalOpen} onClose={() => setDeleteModalOpen(false)} title="Delete World">
            <Stack>
              <Text>This will permanently remove <Text span fw={700}>{world?.name}</Text> and all its documents, stats, rules, and vector data.</Text>
              <Checkbox
                label="I understand this action cannot be undone"
                checked={deleteConfirmed}
                onChange={e => setDeleteConfirmed(e.currentTarget.checked)}
              />
              <Group justify="flex-end">
                <Button variant="default" onClick={() => setDeleteModalOpen(false)}>Cancel</Button>
                <Button color="red" disabled={!deleteConfirmed} loading={deleting} onClick={handleDeleteWorld}>Delete World</Button>
              </Group>
            </Stack>
          </Modal>
        </>
      )}
    </Container>
  );
}
