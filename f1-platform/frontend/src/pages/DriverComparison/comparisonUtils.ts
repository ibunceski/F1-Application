import type { DriverComparisonResponse, LapTime } from '../../types';

export interface SectorStats {
  avg_sector1_ms: number | null;
  avg_sector2_ms: number | null;
  avg_sector3_ms: number | null;
}

export interface QualifyingStats {
  position: number | null;
  gap_to_pole_ms: number | null;
}

export interface RaceStats {
  finishing_position: number | null;
  status: string | null;
  points: number | null;
}

export function recordFor<T>(record: Record<string, unknown>, driverId: number): T {
  return (record[String(driverId)] || {}) as T;
}

export function cleanLapTimes(laps: LapTime[]) {
  return laps
    .filter((lap) => lap.lap_time_ms !== null && !lap.deleted && !lap.is_pit_in_lap && !lap.is_pit_out_lap)
    .map((lap) => lap.lap_time_ms as number);
}

export function sectorStats(comparison: DriverComparisonResponse, driverId: number) {
  return recordFor<SectorStats>(comparison.sector_comparison, driverId);
}

export function qualifyingStats(comparison: DriverComparisonResponse, driverId: number) {
  return recordFor<QualifyingStats>(comparison.qualifying_comparison, driverId);
}

export function raceStats(comparison: DriverComparisonResponse, driverId: number) {
  return recordFor<RaceStats>(comparison.race_result_comparison, driverId);
}
