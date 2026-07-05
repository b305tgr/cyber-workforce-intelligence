import api from "../api/axios";
import type { Professional } from "../types/professional";

export async function getProfessionals(): Promise<Professional[]> {
  const response = await api.get<Professional[]>("/professionals/");
  return response.data;
}