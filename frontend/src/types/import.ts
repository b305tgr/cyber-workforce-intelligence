export interface ImportHistory {
  id: string;
  file_name: string;
  import_type: string;
  total_records: number;
  inserted_records: number;
  duplicate_records: number;
  error_records: number;
  status: string;
  imported_at: string;
}