import { apiClient } from '../lib/api';
import type {
  DriverComparisonResponse,
  DriverTyreStrategy,
  FastestLap,
  LapTimesByDriver,
  PositionChange,
  WeatherSummary,
} from '../types';

export async function getLapTimes(raceId: number, driverId?: number): Promise<LapTimesByDriver[]> {
  const { data } = await apiClient.get<LapTimesByDriver[]>(`/analysis/races/${raceId}/laps`, {
    params: driverId ? { driver_id: driverId } : undefined,
  });
  return data;
}

export async function getTyreStrategy(raceId: number): Promise<DriverTyreStrategy[]> {
  const { data } = await apiClient.get<DriverTyreStrategy[]>(`/analysis/races/${raceId}/tyre-strategy`);
  return data;
}

export async function getPositionChanges(raceId: number): Promise<PositionChange[]> {
  const { data } = await apiClient.get<PositionChange[]>(`/analysis/races/${raceId}/position-changes`);
  return data;
}

export async function compareDrivers(
  raceId: number,
  driver1Id: number,
  driver2Id: number,
): Promise<DriverComparisonResponse> {
  const { data } = await apiClient.get<DriverComparisonResponse>(`/analysis/races/${raceId}/compare`, {
    params: { driver1_id: driver1Id, driver2_id: driver2Id },
  });
  return data;
}

export async function getWeather(raceId: number): Promise<WeatherSummary> {
  const { data } = await apiClient.get<WeatherSummary>(`/analysis/races/${raceId}/weather`);
  return data;
}

export async function getFastestLaps(raceId: number): Promise<FastestLap[]> {
  const { data } = await apiClient.get<FastestLap[]>(`/analysis/races/${raceId}/fastest-laps`);
  return data;
}
