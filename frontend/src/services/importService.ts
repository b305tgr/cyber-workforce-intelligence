import api from "../api/axios";
import type { ImportHistory } from "../types/import";

export async function getImportHistory(): Promise<ImportHistory[]> {
  const response = await api.get<ImportHistory[]>(
    "/imports/history"
  );

  return response.data;
}