export interface ColumnInfo {
  name: string;
  type: string;
}

export interface TableStatus {
  class_name: string;
  table_name: string;
  table_exists: boolean;
  record_count: number | null;
  schema_status: "ok" | "drift" | "missing";
  columns_in_model: ColumnInfo[];
  table_columns: ColumnInfo[];
  missing_columns: string[];
  extra_columns: string[];
}

export interface DbStatusResponse {
  tables: TableStatus[];
}

export interface SyncResult {
  added_columns: string[];
  dropped_columns: string[];
}

export interface ReindexResult {
  success: boolean;
  documents_indexed: number;
  error: string | null;
}
