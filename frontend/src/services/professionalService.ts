import api from "../api/axios";
import type { Professional } from "../types/professional";

export interface CreateProfessionalRequest {
  full_name: string;
  current_title: string;
  years_experience: number;
  current_company_id: string | null;
  location_id: string | null;
}

export interface UpdateProfessionalRequest {
  full_name: string;
  current_title: string;
  years_experience: number;
  current_company_id: string | null;
  location_id: string | null;
}

export async function getProfessionals(): Promise<Professional[]> {
  const response = await api.get<Professional[]>("/professionals/");
  return response.data;
}

export async function getProfessional(
  id: string,
): Promise<Professional> {
  const response = await api.get<Professional>(
    `/professionals/${id}`,
  );

  return response.data;
}

export async function createProfessional(
  professional: CreateProfessionalRequest,
): Promise<Professional> {
  const response = await api.post<Professional>(
    "/professionals/",
    professional,
  );

  return response.data;
}

export async function updateProfessional(
  id: string,
  professional: UpdateProfessionalRequest,
): Promise<Professional> {
  const response = await api.put<Professional>(
    `/professionals/${id}`,
    professional,
  );

  return response.data;
}

export async function deleteProfessional(
  id: string,
): Promise<void> {
  await api.delete(
    `/professionals/${id}`,
  );
}