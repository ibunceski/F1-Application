import { apiClient } from '../lib/api';
import type { Driver } from '../types';

export interface DriverSeasonStats {
  driver_id: number;
  season: number;
  races_entered: number;
  avg_finish: number | null;
  best_finish: number | null;
  dnf_count: number;
  total_points: number;
  wins: number;
  podiums: number;
  top10s: number;
}

export async function getDriversBySeason(year?: number): Promise<Driver[]> {
  const { data } = await apiClient.get<Driver[]>('/drivers', { params: year ? { season: year } : undefined });
  return data;
}

export async function getDriverById(id: number): Promise<Driver> {
  const { data } = await apiClient.get<Driver>(`/drivers/${id}`);
  return data;
}

export async function getDriverStats(id: number, year: number): Promise<DriverSeasonStats> {
  const { data } = await apiClient.get<DriverSeasonStats>(`/drivers/${id}/stats`, { params: { season: year } });
  return data;
}
