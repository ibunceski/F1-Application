import { apiClient } from '../lib/api';
import type { QualifyingResult, Race, RaceResult } from '../types';

export async function getRacesBySeason(year: number): Promise<Race[]> {
  const { data } = await apiClient.get<Race[]>('/races', { params: { season: year } });
  return data;
}

export async function getRaceById(id: number): Promise<Race> {
  const { data } = await apiClient.get<Race>(`/races/${id}`);
  return data;
}

export async function getRaceQualifying(id: number): Promise<QualifyingResult[]> {
  const { data } = await apiClient.get<QualifyingResult[]>(`/races/${id}/qualifying`);
  return data;
}

export async function getRaceResults(id: number): Promise<RaceResult[]> {
  const { data } = await apiClient.get<RaceResult[]>(`/races/${id}/results`);
  return data;
}

export async function getNextRace(): Promise<Race> {
  const { data } = await apiClient.get<Race>('/races/next');
  return data;
}
