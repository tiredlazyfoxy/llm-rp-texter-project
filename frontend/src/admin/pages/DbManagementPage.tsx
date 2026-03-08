import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import {
  IconDownload,
  IconPlus,
  IconRefresh,
  IconUpload,
} from "@tabler/icons-react";
import type { TableStatus } from "../../types/dbManagement";
import { createTable, exportDb, getDbStatus, importDb, syncTable } from "../../api/dbManagement";

// ---------------------------------------------------------------------------
// Schema detail modal
// ---------------------------------------------------------------------------

interface SchemaDetailModalProps {
  opened: boolean;
  table: TableStatus | null;
  onClose: () => void;
  onSync: (tableName: string) => void;
  syncLoading: boolean;
}

function SchemaDetailModal({ opened, table, onClose, onSync, syncLoading }: SchemaDetailModalProps) {
  if (!table) return null;

  const missingSet = new Set(table.missing_columns);
  const extraSet = new Set(table.extra_columns);
  const hasDrift = table.missing_columns.length > 0 || table.extra_columns.length > 0;

  return (
    <Modal opened={opened} onClose={onClose} title={`Schema: ${table.class_name}`} size="lg">
      <Stack>
        <Group grow align="flex-start">
          <div>
            <Text fw={600} size="sm" mb="xs">Model Fields</Text>
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Type</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {table.columns_in_model.map((f) => (
                  <Table.Tr
                    key={f.name}
                    style={missingSet.has(f.name) ? { background: "var(--mantine-color-yellow-light)" } : undefined}
                  >
                    <Table.Td>
                      <Text size="xs">{f.name}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" c="dimmed">{f.type}</Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </div>

          <div>
            <Text fw={600} size="sm" mb="xs">Table Columns</Text>
            {table.table_columns.length === 0 ? (
              <Text size="sm" c="dimmed">Table does not exist</Text>
            ) : (
              <Table striped>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Name</Table.Th>
                    <Table.Th>Type</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {table.table_columns.map((c) => (
                    <Table.Tr
                      key={c.name}
                      style={extraSet.has(c.name) ? { background: "var(--mantine-color-gray-light)" } : undefined}
                    >
                      <Table.Td>
                        <Text size="xs">{c.name}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="xs" c="dimmed">{c.type}</Text>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </div>
        </Group>

        {table.missing_columns.length > 0 && (
          <Text size="xs" c="yellow">
            Missing in table: {table.missing_columns.join(", ")}
          </Text>
        )}
        {table.extra_columns.length > 0 && (
          <Text size="xs" c="dimmed">
            Extra in table: {table.extra_columns.join(", ")}
          </Text>
        )}

        {hasDrift && (
          <Button
            variant="light"
            leftSection={<IconRefresh size={14} />}
            loading={syncLoading}
            onClick={() => onSync(table.table_name)}
          >
            Sync Schema
          </Button>
        )}
      </Stack>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const color = status === "ok" ? "green" : status === "drift" ? "yellow" : "red";
  const label = status === "ok" ? "OK" : status === "drift" ? "Drift" : "Missing";
  return <Badge variant="light" size="sm" color={color}>{label}</Badge>;
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function DbManagementPage() {
  const [tables, setTables] = useState<TableStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Schema detail modal
  const [detailTarget, setDetailTarget] = useState<TableStatus | null>(null);

  // Hidden file input for import
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setTables(await getDbStatus());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load DB status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleExport = async () => {
    setActionLoading("export");
    setError(null);
    try {
      await exportDb();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setActionLoading(null);
    }
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";

    if (!window.confirm("Import will overwrite existing data. Continue?")) return;

    setActionLoading("import");
    setError(null);
    try {
      await importDb(file);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setActionLoading(null);
    }
  };

  const handleCreateTable = async (tableName: string) => {
    setActionLoading(tableName);
    setError(null);
    try {
      await createTable(tableName);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create table");
    } finally {
      setActionLoading(null);
    }
  };

  const handleSync = async (tableName: string) => {
    setActionLoading(`sync:${tableName}`);
    setError(null);
    try {
      await syncTable(tableName);
      setDetailTarget(null);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>Database</Title>
        <Group gap="xs">
          <Button
            variant="light"
            size="sm"
            leftSection={<IconDownload size={16} />}
            onClick={handleExport}
            loading={actionLoading === "export"}
          >
            Export All
          </Button>
          <Button
            variant="light"
            size="sm"
            leftSection={<IconUpload size={16} />}
            onClick={handleImportClick}
            loading={actionLoading === "import"}
          >
            Import
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".zip"
            style={{ display: "none" }}
            onChange={handleImportFile}
          />
        </Group>
      </Group>

      {error && (
        <Alert color="red" mb="md" withCloseButton onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Group justify="center" py="xl"><Loader /></Group>
      ) : tables.length === 0 ? (
        <Text c="dimmed" ta="center" py="xl">No registered models found.</Text>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Class</Table.Th>
              <Table.Th>Table</Table.Th>
              <Table.Th>Records</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th w={140}>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {tables.map((t) => (
              <Table.Tr key={t.table_name}>
                <Table.Td><Text size="sm" fw={500}>{t.class_name}</Text></Table.Td>
                <Table.Td><Text size="sm" c="dimmed">{t.table_name}</Text></Table.Td>
                <Table.Td>
                  <Text size="sm">{t.record_count !== null ? t.record_count : "—"}</Text>
                </Table.Td>
                <Table.Td>
                  <StatusBadge status={t.schema_status} />
                </Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    {t.schema_status === "missing" && (
                      <Button
                        variant="light"
                        size="compact-xs"
                        leftSection={<IconPlus size={12} />}
                        loading={actionLoading === t.table_name}
                        onClick={() => handleCreateTable(t.table_name)}
                      >
                        Create
                      </Button>
                    )}
                    {t.schema_status === "drift" && (
                      <Button
                        variant="subtle"
                        size="compact-xs"
                        onClick={() => setDetailTarget(t)}
                      >
                        Details
                      </Button>
                    )}
                    {t.schema_status === "ok" && (
                      <Button
                        variant="subtle"
                        size="compact-xs"
                        c="dimmed"
                        onClick={() => setDetailTarget(t)}
                      >
                        Schema
                      </Button>
                    )}
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <SchemaDetailModal
        opened={detailTarget !== null}
        table={detailTarget}
        onClose={() => setDetailTarget(null)}
        onSync={handleSync}
        syncLoading={detailTarget !== null && actionLoading === `sync:${detailTarget.table_name}`}
      />
    </Container>
  );
}
