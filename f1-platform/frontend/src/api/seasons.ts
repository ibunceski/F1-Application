import { apiClient } from '../lib/api';
import type { Season, SeasonStats } from '../types';

export async function getSeasons(): Promise<Season[]> {
  const { data } = await apiClient.get<Season[]>('/seasons');
  return data;
}

export async function getSeasonByYear(year: number): Promise<Season> {
  const { data } = await apiClient.get<Season>(`/seasons/${year}`);
  return data;
}

export async function getSeasonStats(year: number): Promise<SeasonStats> {
  const { data } = await apiClient.get<SeasonStats>(`/seasons/${year}/stats`);
  return data;
}
